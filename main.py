import re
import os
import json
import logging
from pathlib import Path
from tqdm import tqdm
from bilancio_parser import BilancioParser
from excel_exporter import ExcelExporter


def setup_logging():
    """
    Configure logging system for the financial statement parser.
    
    Sets up console logging.
    The parser.log file creation has been removed for pubblic beta release,
    leaving only the unmatched_items.log which is created by the parser modules when needed.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()  # Console output only
        ]
    )


def process_pdfs_in_folder(folder_path: Path, output_folder: Path, config_path: Path):
    """
    Process all PDF files in a folder.
    
    The retry mechanism handles non-deterministic behavior in fuzzy matching by
    attempting parsing up to 3 times and using the best result.
    
    Args:
        folder_path: Directory containing PDF files to process
        output_folder: Directory for output files
        config_path: Path to configuration (directory for modular config)
    """
    if not output_folder.exists():
        output_folder.mkdir(parents=True)

    # Initialize parser and exporter once and reuse them
    # This prevents redundant configuration loading on every retry attempt
    parser = BilancioParser(config_path)
    exporter = ExcelExporter()
    
    # Find all PDF files to process
    pdf_files = list(folder_path.glob('*.pdf'))
    
    if not pdf_files:
        logging.warning(f"No PDF files found in folder '{folder_path}'.")
        return

    logging.info(f"Found {len(pdf_files)} PDF files to process.")

    # Process each PDF file with retry logic
    for pdf_path in tqdm(pdf_files, desc="Processing Financial Statements"):
        logging.info(f"--- Starting processing of: {pdf_path.name} ---")
        
        # === RETRY MECHANISM FOR NON-DETERMINISTIC BEHAVIOR ===
        # NOTE: The parser sometimes produces non-deterministic results due to
        # ambiguities in fuzzy matching. While awaiting a definitive fix in the
        # core parser logic, we implement a retry system. If parsing fails or
        # succeeds with tolerance, it's retried up to 3 times. If one attempt
        # achieves full success, that result is used. Otherwise, the first
        # attempt result is saved.
        
        first_attempt_result = None
        final_result = None
        max_attempts = 3

        for attempt in range(max_attempts):
            logging.info(f"Attempt {attempt + 1} of {max_attempts} for '{pdf_path.name}'...")
            
            # Reuse the same parser instance instead of recreating
            # This eliminates redundant configuration loading and improves performance
            current_result = parser.parse(pdf_path)

            if attempt == 0:
                first_attempt_result = current_result  # Always save first result

            if not current_result:  # Critical parsing failure
                logging.warning(f"Attempt {attempt + 1} failed (critical error).")
                continue

            validation_status = current_result.get('validazioni', {}).get('summary', {}).get('status', 'failed')
            
            if validation_status == 'success':
                logging.info(f"✅ Attempt {attempt + 1} succeeded with full success!")
                final_result = current_result
                break  # Exit loop if perfect result found
            else:
                logging.warning(f"Attempt {attempt + 1} completed with status: {validation_status.upper()}. Will retry if possible.")

        # Use first attempt result if no perfect result was achieved
        if final_result is None:
            logging.warning(f"No attempt achieved full success. Using first attempt result.")
            final_result = first_attempt_result
        
        # === END RETRY MECHANISM ===

        if final_result:
            # Get output settings from parser configuration
            output_settings = parser.config_manager.get_output_settings()
            prefixes = output_settings.get('output_prefixes', {})

            # Determine file prefix based on COMBINED validation status (Parser + Reclassification)
            prefix = prefixes.get('success', '')

            # Get parser validation status
            parser_status = final_result.get('validazioni', {}).get('summary', {}).get('status', 'success')

            # Get reclassification validation status
            reclassification_data = final_result.get('reclassification', {})
            reclassify_status = 'success'  # Default if reclassification not available

            if reclassification_data.get('success', False):
                # Check reclassification balance sheet validation
                balance_validation = reclassification_data.get('balance_sheet_validation', {})
                reclassify_status = balance_validation.get('status', 'success')
            elif reclassification_data.get('success') is False:
                reclassify_status = 'failed'

            # Combine statuses for final determination
            if parser_status == 'failed' or reclassify_status == 'failed':
                prefix = prefixes.get('failed', '')
            elif parser_status == 'success_with_tolerance' or reclassify_status == 'success_with_tolerance':
                prefix = prefixes.get('success_with_tolerance', '')
            # else: success + success = prefix already set above

            # Define output file paths with combined status naming
            base_filename = f"{prefix}{pdf_path.stem}"
            excel_output_path = output_folder / f"{base_filename}.xlsx"

            try:
                # Generate Excel file using updated exporter
                exporter.export(final_result, str(excel_output_path))
                
                # Log combined status
                combined_status = 'SUCCESS' if not prefix else ('SUCCESS_WITH_TOLERANCE' if 'SuccessWithTol' in prefix else 'FAILED')
                logging.info(f"✅ Results for '{pdf_path.name}' (Parser: {parser_status.upper()}, Reclassify: {reclassify_status.upper()}, Final: {combined_status}) saved in Excel.\n")
            except Exception as e:
                logging.error(f"❌ Unable to save output files for '{pdf_path.name}': {e}")

def main():
    """    
    Sets up the environment, validates directory structure, and initiates
    processing using the refactored modular parser architecture.
    """
    setup_logging()
    
    # Define directory structure
    current_directory = Path(__file__).parent.resolve()
    pdf_folder = current_directory / 'bilanci'
    output_folder = current_directory / 'output'
    
    # Use modular configuration directory instead of single config.yaml
    # The system will first look for modular config directory, then fallback to config.yaml
    config_directory = current_directory / 'config'
    config_file = current_directory / 'config.yaml'
    
    # Determine which configuration to use
    if config_directory.exists() and any(config_directory.glob('config_*.yaml')):
        config_path = config_directory
        logging.info("Using modular configuration from 'config' directory")
    elif config_file.exists():
        config_path = config_file
        logging.info("Using legacy single configuration file 'config.yaml'")
    else:
        logging.error("No configuration found. Please provide either 'config' directory with modular configs or 'config.yaml' file.")
        return

    # Validate PDF input directory
    if not pdf_folder.exists() or not any(pdf_folder.iterdir()):
        pdf_folder.mkdir(exist_ok=True)
        logging.warning(f"The folder '{pdf_folder}' is empty or does not exist. Place your PDF files here for processing.")
    else:
        # Process all PDFs in the folder
        process_pdfs_in_folder(pdf_folder, output_folder, config_path)


if __name__ == '__main__':
    main()