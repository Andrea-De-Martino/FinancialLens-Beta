import pdfplumber
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

# Import all the specialized modules
from configuration_manager import ConfigurationManager
from pdf_extractor import PDFExtractor
from text_processor import TextProcessor
from hierarchy_manager import HierarchyManager
from enrichment_engine import EnrichmentEngine
from data_validator import DataValidator
from financial_reclassifier import FinancialReclassifier


class BilancioParser:
    """
    Main orchestrator for financial statement parsing with integrated reclassification.
    
    This class represents the enhanced version of the financial statement parser,
    now equipped with sophisticated reclassification capabilities that transform
    Italian financial statements into international format. The parser maintains
    100% functional equivalence with the original implementation while adding
    powerful analytical features.
    
    The parser orchestrates a comprehensive financial analysis pipeline:
    - PDF extraction and text processing with fuzzy matching
    - Hierarchical data construction with parent-child relationships  
    - Nota Integrativa enrichment for abbreviated format documents
    - Mathematical validation with tolerance handling
    - Financial reclassification into international P&L, Assets, Liabilities format
    - Professional Excel output with integrated analysis
    
    The modular architecture enables better separation of concerns while maintaining
    the carefully tuned behavior of the original system. All parsing logic,
    validation rules, and output formats remain identical to preserve the
    sophisticated financial statement processing capabilities.
    
    The integrated reclassification transforms Italian accounting structures into
    standardized international formats suitable for cross-border analysis,
    investment evaluation, and financial modeling while maintaining full
    audit trails and calculation transparency.
    """

    def __init__(self, config_path: Path):
        """
        Initialize parser with configuration and integrated reclassification capabilities.
        
        Maintains the same constructor signature and behavior as the original
        parser while internally setting up the enhanced modular architecture
        including the new financial reclassification engine.
        
        Args:
            config_path: Path to configuration file or directory
        """
        # Initialize configuration manager and load all configurations
        self.config_manager = ConfigurationManager(config_path)
        
        if not self.config_manager.validate_configuration():
            raise ValueError("Invalid configuration detected")
        
        # Initialize specialized modules with their required configurations
        self.pdf_extractor = PDFExtractor(
            self.config_manager.get_pdf_extractor_config()
        )
        
        self.text_processor = TextProcessor(
            self.config_manager.get_text_processor_config()
        )
        
        self.hierarchy_manager = HierarchyManager(
            self.config_manager.get_hierarchy_config()
        )
        
        self.enrichment_engine = EnrichmentEngine(
            self.config_manager.get_enrichment_config()
        )
        
        self.data_validator = DataValidator(
            self.config_manager.get_validation_config()
        )
        
        # Initialize financial reclassifier with enhanced capabilities
        self.financial_reclassifier = FinancialReclassifier(
            self.config_manager.get_reclassifier_config()
        )
        
        # Validate all module configurations
        if not self._validate_module_configurations():
            raise ValueError("Module configuration validation failed")

    def parse(self, pdf_path: Path) -> Optional[Dict]:
        """
        Parse PDF financial statement with integrated reclassification analysis.
        
        This method preserves the exact same public interface, processing logic,
        and output format as the original parser while adding sophisticated
        reclassification capabilities. The enhanced processing flow includes
        all original features plus international format transformation.
        
        The comprehensive processing sequence:
        1. PDF extraction and section detection
        2. Text processing and hierarchical parsing  
        3. Data map building and consolidation
        4. Nota Integrativa enrichment (if applicable)
        5. Final hierarchical structure construction
        6. Mathematical validation and consistency checking
        7. 🆕 Financial reclassification into international format
        8. Enhanced output formatting with integrated analysis
        
        Args:
            pdf_path: Path to PDF file to parse
            
        Returns:
            Complete financial statement data dictionary with reclassification results
            or None if parsing fails (maintains original interface)
        """
        file_basename = pdf_path.name
        
        try:
            # Step 1: Extract raw data from PDF document
            logging.info(f"Starting comprehensive financial analysis for {file_basename}")
            extraction_result = self.pdf_extractor.extract_document_data(pdf_path)
            
            if not extraction_result.tables:
                logging.error(f"No tabular data extracted from {file_basename}. Analysis terminated.")
                return None
            
            # Step 2: Process financial items and build hierarchy
            flat_data = self._process_financial_items(extraction_result)
            
            if not flat_data:
                logging.error(f"No financial items processed from {file_basename}.")
                return None
            
            # Step 3: Build consolidated data map
            data_map = self._build_data_map(flat_data)
            
            # Step 4: Apply enrichment for abbreviated format documents
            if extraction_result.is_abbreviated_format:
                with pdfplumber.open(pdf_path) as pdf:
                    enriched_map = self.enrichment_engine.enrich_abbreviated_data(
                        data_map, pdf, extraction_result.ni_start_page
                    )
            else:
                enriched_map = data_map
            
            # Step 5: Build final hierarchical structure
            structured_data = self._build_final_structure(enriched_map)
            
            # Step 6: Prepare output with metadata
            output = {
                "metadata": {
                    "file_name": file_basename,
                    "anno_bilancio": extraction_result.document_year
                },
                **structured_data,
                "testi_allegati": {
                    section.title: section.content 
                    for section in extraction_result.sections.values()
                }
            }
            
            # Step 7: Perform mathematical validations
            output["validazioni"] = self.data_validator.perform_validations(output)
            
            # Step 8: 🆕 Enhanced Financial Reclassification
            reclassification_result = self._perform_financial_reclassification(output)
            
            # Step 9: Integrate reclassification results into output
            if reclassification_result.success:
                output["reclassification"] = {
                    "success": True,
                    "reclassified_data": reclassification_result.reclassified_data,
                    "reclassified_details": reclassification_result.reclassified_details,
                    "balance_sheet_validation": reclassification_result.balance_sheet_validation,
                    "orphan_voices_count": reclassification_result.orphan_voices_count
                }
                logging.info("Financial reclassification completed successfully")
            else:
                output["reclassification"] = {
                    "success": False,
                    "error": "Reclassification process failed"
                }
                logging.warning("Financial reclassification failed - continuing with standard output")
            
            # Step 10: Final status reporting
            parser_status = output["validazioni"]["summary"]["status"].upper()
            reclassification_status = "SUCCESS" if reclassification_result.success else "FAILED"
            
            logging.info(f"Financial analysis completed for {file_basename}:")
            logging.info(f"  - Parser Status: {parser_status}")
            logging.info(f"  - Reclassification Status: {reclassification_status}")
            
            return output
            
        except Exception as e:
            logging.error(f"Fatal error during comprehensive analysis of {pdf_path.name}: {e}", exc_info=True)
            return None

    def _perform_financial_reclassification(self, financial_data: Dict[str, Any]) -> Any:
        """
        Perform sophisticated financial reclassification analysis.
        
        This method orchestrates the transformation of Italian financial statement
        data into international format using the integrated FinancialReclassifier.
        The reclassification process includes mapping Italian accounting items to
        international equivalents, performing cascading calculations, and validating
        balance sheet equilibrium using the same tolerance logic as the main parser.
        
        The reclassification is performed as an enhancement to the standard parsing
        process and does not affect the core financial data if it fails. This ensures
        backward compatibility and robust operation even with incomplete mapping
        configurations.
        
        Args:
            financial_data: Complete parsed financial statement data
            
        Returns:
            ReclassificationResult containing transformed data and validation results
        """
        try:
            logging.info("Initiating financial reclassification analysis")
            
            # Validate reclassifier configuration before processing
            if not self.financial_reclassifier.validate_configuration():
                logging.warning("Reclassifier configuration validation failed - skipping reclassification")
                return self._create_failed_reclassification_result("Configuration validation failed")
            
            # Execute comprehensive reclassification process
            reclassification_result = self.financial_reclassifier.reclassify_financial_data(financial_data)
            
            if reclassification_result.success:
                # Log reclassification summary statistics
                orphan_count = reclassification_result.orphan_voices_count
                balance_status = reclassification_result.balance_sheet_validation.get('status', 'unknown')
                
                logging.info(f"Reclassification analysis summary:")
                logging.info(f"  - Balance Sheet Validation: {balance_status.upper()}")
                logging.info(f"  - Unmapped Voices: {orphan_count} items")
                
                if orphan_count > 0:
                    logging.info(f"Note: {orphan_count} financial items could not be mapped to international format")
                
                return reclassification_result
            else:
                logging.error("Reclassification process reported failure")
                return reclassification_result
                
        except Exception as e:
            logging.error(f"Reclassification analysis failed with exception: {e}")
            return self._create_failed_reclassification_result(f"Exception during processing: {str(e)}")

    def _create_failed_reclassification_result(self, error_message: str) -> Any:
        """
        Create a failed reclassification result for error handling.
        
        Args:
            error_message: Description of the failure
            
        Returns:
            ReclassificationResult indicating failure
        """
        # Import here to avoid circular imports
        from financial_reclassifier import ReclassificationResult
        
        return ReclassificationResult(
            success=False,
            reclassified_data={},
            reclassified_details={},
            balance_sheet_validation={},
            orphan_voices_count=0
        )

    def _process_financial_items(self, extraction_result) -> List[Dict[str, Any]]:
        """
        Process financial items from PDF extraction result.
        
        This method replicates the core processing logic from the original
        parser's _extract_flat_data method. It iterates through the document
        page by page, determines the financial context, and processes tables
        accordingly, including parent stack management and hierarchical
        relationship building.
        
        Args:
            extraction_result: Result from PDF extraction containing tables and metadata
            
        Returns:
            List of processed financial items with hierarchical information
        """
        flat_data: List[Dict[str, Any]] = []
        current_context: Optional[str] = None

        # Initialize the hierarchy context, which contains the parent_stack
        hierarchy_context = self.hierarchy_manager.create_hierarchy_context(
            current_context=current_context,
            is_abbreviated_format=extraction_result.is_abbreviated_format
        )

        # Process the document page by page to ensure correct context switching.
        # This loop structure is critical to replicate the original parser's behavior.
        for page_num, page_text in enumerate(extraction_result.pages_text):
            # Stop processing at the calculated boundary, which could be
            # the Nota Integrativa, Rendiconto Finanziario, or another section.
            # This prevents the parser from reading tables outside the main financial statements.
            if extraction_result.parsing_boundary_page != -1 and page_num >= extraction_result.parsing_boundary_page:
                logging.info(f"Reached parsing boundary on page {page_num + 1}. Halting main processing.")
                break

            # Detect context for the current page.
            new_context = self._detect_section_context(page_text)

            # If a new context is detected (e.g., changing from Balance Sheet to Income Statement),
            # finalize the previous section's hierarchy before switching.
            if new_context and new_context != current_context:
                logging.info(f"Context changed from '{current_context}' to '{new_context}' on page {page_num + 1}.")
                
                # Finalize the hierarchy for the previous section.
                self.hierarchy_manager.finalize_hierarchy_context(hierarchy_context)
                
                # Update the context for the new section.
                current_context = new_context
                hierarchy_context.current_context = current_context

            # Skip pages where no financial context has been established.
            if not current_context:
                continue

            # Filter to get only the tables that belong to the current page.
            tables_on_page = [tbl for tbl in extraction_result.tables if tbl.page_number == page_num]

            for table_data in tables_on_page:
                table = table_data.data
                layout_info = table_data.layout_info

                # Skip processing if table layout information is missing.
                if not layout_info:
                    continue

                desc_col, val_col = layout_info['desc_col'], layout_info['value_col']
                
                for row in table:
                    if len(row) <= max(desc_col, val_col) or not row[desc_col]:
                        continue
                    
                    raw_desc = row[desc_col] or ""
                    # A single cell can contain multiple logical lines separated by newlines.
                    logical_lines = [line.strip() for line in raw_desc.split('\n') if line.strip()]
                    
                    if not logical_lines:
                        continue
                    
                    # Process each logical line within the description cell.
                    for i, line_desc in enumerate(logical_lines):

                        # For abbreviated formats, check for maturity breakdown lines (entro/oltre)
                        # before attempting to match as a standard financial item.
                        if extraction_result.is_abbreviated_format and hierarchy_context.parent_stack:
                            # The value is only associated with the last logical line in a cell.
                            value_for_check = self._parse_value(row[val_col]) if i == len(logical_lines) - 1 else 0.0
                            
                            # Create a temporary dictionary for this check.
                            temp_item_data = {"voce_originale": line_desc, "valore": value_for_check}
                            
                            # If the HierarchyManager handles the line as a maturity detail,
                            # skip to the next line.
                            if self.hierarchy_manager.handle_abbreviated_scadenze(temp_item_data, hierarchy_context.parent_stack):
                                continue

                        if self.text_processor.is_ignorable_text(line_desc):
                            continue
                        
                        # Find potential matches for the line using the correct context.
                        candidates = self.text_processor.find_best_matches(line_desc, current_context)
                        if not candidates:
                            continue
                        
                        # Disambiguate candidates using the current hierarchical context.
                        disambiguation_context = self.text_processor.create_disambiguation_context(
                            hierarchy_context.parent_stack
                        )
                        match_voce, score = self.text_processor.disambiguate_candidates(
                            candidates, disambiguation_context
                        )
                        
                        if score < self.text_processor.get_fuzzy_score_threshold():
                            continue
                        
                        # Extract the value (only for the last logical line in a multi-line description).
                        valore_riga = self._parse_value(row[val_col]) if i == len(logical_lines) - 1 else 0.0
                        
                        config_node = self.hierarchy_manager._get_config_node(match_voce)
                        is_potential_parent = config_node and 'dettaglio' in config_node

                        valore_da_assegnare = 0.0 if is_potential_parent and valore_riga == 0.0 else valore_riga

                        item_data = {
                            "voce_originale": self.text_processor.normalize_text(line_desc),
                            "voce_canonica": match_voce,
                            "valore": valore_da_assegnare,
                            "score": score,
                            "contesto": current_context,
                            "page_num": page_num
                        }
                        
                        # Process the item through the hierarchy manager to update the parent stack.
                        hierarchy_context = self.hierarchy_manager.process_financial_item(
                            item_data, hierarchy_context
                        )
                        
                        flat_data.append(item_data)
        
        # Finalize the hierarchy for the last processed section.
        self.hierarchy_manager.finalize_hierarchy_context(hierarchy_context)
        
        return flat_data

    def _detect_section_context(self, page_text: str) -> Optional[str]:
        """
        Detect financial statement section from page text.
        
        Preserves the exact section detection logic from the original parser.
        
        Args:
            page_text: Text content of the page
            
        Returns:
            Section name or None if not detected
        """
        import re
        
        section_patterns = {
            'stato_patrimoniale': re.compile(r'\b(stato\s+patrimoniale)\b', re.IGNORECASE),
            'conto_economico': re.compile(r'\b(conto\s+economico)\b', re.IGNORECASE)
        }
        
        for section_name, pattern in section_patterns.items():
            if pattern.search(page_text):
                return section_name
        
        return None

    def _build_data_map(self, flat_data: List[Dict[str, Any]]) -> Dict[str, Dict]:
        """
        Build consolidated data map from flat financial items.
        
        Preserves the exact _build_data_map logic from the original parser,
        including deduplication and value preservation rules.
        
        Args:
            flat_data: List of processed financial items
            
        Returns:
            Dictionary mapping canonical names to item data
        """
        data_map: Dict[str, Dict] = {}
        
        for item in flat_data:
            key = item['voce_canonica']
            
            # Clean up temporary hierarchy data
            if '_children_buffer' in item:
                del item['_children_buffer']
            
            # Use new item if not exists, or if new item has non-zero value and existing has zero
            if (key not in data_map or 
                (item.get('valore', 0.0) != 0.0 and data_map[key].get('valore') == 0.0)):
                data_map[key] = item
        
        return data_map

    def _build_final_structure(self, data_map: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Build final hierarchical structure from data map.
        
        Constructs the complete financial statement structure using the
        hierarchy manager and configuration schema.
        
        Args:
            data_map: Flat data map to structure
            
        Returns:
            Hierarchical financial statement structure
        """
        structured_data: Dict[str, Any] = {}
        
        # Get full configuration for structure building
        full_config = self.config_manager.get_full_config()
        
        # Build Balance Sheet structure
        if 'stato_patrimoniale' in full_config:
            sp_config = full_config['stato_patrimoniale']
            sp_data = {}
            
            if 'attivo' in sp_config:
                sp_data['attivo'] = self.hierarchy_manager.build_hierarchical_structure(
                    sp_config['attivo'], data_map
                )
            
            if 'passivo' in sp_config:
                sp_data['passivo'] = self.hierarchy_manager.build_hierarchical_structure(
                    sp_config['passivo'], data_map
                )
            
            if sp_data:
                structured_data['stato_patrimoniale'] = sp_data
        
        # Build Income Statement structure
        if 'conto_economico' in full_config:
            ce_data = self.hierarchy_manager.build_hierarchical_structure(
                full_config['conto_economico'], data_map
            )
            if ce_data:
                structured_data['conto_economico'] = ce_data
        
        return structured_data

    def _parse_value(self, value_str: Optional[str]) -> float:
        """
        Parse value string to float exactly as original parser.
        
        Preserves the exact _parse_value logic including all edge cases.
        
        Args:
            value_str: String value to parse
            
        Returns:
            Parsed float value or 0.0 if parsing fails
        """
        if not value_str or str(value_str).strip() in ['-', '']:
            return 0.0
        
        clean_str = str(value_str).strip().replace('\n', ' ').replace('.', '').replace(',', '.')
        if clean_str.startswith('(') and clean_str.endswith(')'):
            clean_str = '-' + clean_str[1:-1]
        
        import re
        numeric_part = re.search(r'^-?[\d.]+', clean_str)
        if not numeric_part:
            return 0.0
        
        try:
            return float(numeric_part.group(0))
        except (ValueError, TypeError):
            return 0.0

    def _validate_module_configurations(self) -> bool:
        """
        Validate that all modules have valid configurations.
        
        Ensures that all specialized modules including the new financial
        reclassifier are properly configured and ready for processing operations.
        
        Returns:
            True if all module configurations are valid, False otherwise
        """
        modules_to_validate = [
            ('TextProcessor', self.text_processor),
            ('EnrichmentEngine', self.enrichment_engine),
            ('FinancialReclassifier', self.financial_reclassifier)
        ]
        
        for module_name, module_instance in modules_to_validate:
            if hasattr(module_instance, 'validate_configuration'):
                if not module_instance.validate_configuration():
                    logging.error(f"{module_name} configuration validation failed")
                    return False
        
        return True

    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the parser configuration and capabilities.
        
        Provides analytical information about the parser setup including the
        new reclassification capabilities for debugging and monitoring purposes.
        
        Returns:
            Dictionary containing parser statistics and configuration info
        """
        stats = {
            'parser_version': 'Enhanced Architecture v2.0',
            'modules_loaded': [
                'ConfigurationManager',
                'PDFExtractor', 
                'TextProcessor',
                'HierarchyManager',
                'EnrichmentEngine',
                'DataValidator',
                'FinancialReclassifier'  # New module
            ],
            'features': [
                'Italian Financial Statement Parsing',
                'Hierarchical Data Construction',
                'Nota Integrativa Enrichment',
                'Mathematical Validation',
                'International Format Reclassification'  # New feature
            ]
        }
        
        # Add module-specific statistics if available
        if hasattr(self.text_processor, 'get_available_contexts'):
            stats['available_contexts'] = self.text_processor.get_available_contexts()
        
        if hasattr(self.enrichment_engine, 'get_enrichment_statistics'):
            stats['enrichment_stats'] = self.enrichment_engine.get_enrichment_statistics()
        
        if hasattr(self.financial_reclassifier, 'get_reclassification_statistics'):
            stats['reclassification_stats'] = self.financial_reclassifier.get_reclassification_statistics()
        
        return stats

    def validate_system_integrity(self) -> bool:
        """
        Validate overall system integrity including reclassification capabilities.
        
        Performs comprehensive validation of the entire parsing system including
        the new financial reclassification engine to ensure all components are
        properly initialized and configured.
        
        Returns:
            True if system integrity is validated, False otherwise
        """
        try:
            # Validate configuration manager
            if not self.config_manager.validate_configuration():
                logging.error("Configuration manager validation failed")
                return False
            
            # Validate module configurations
            if not self._validate_module_configurations():
                logging.error("Module configuration validation failed")
                return False
            
            # Validate text processor contexts
            available_contexts = self.text_processor.get_available_contexts()
            expected_contexts = ['stato_patrimoniale', 'conto_economico']
            missing_contexts = [ctx for ctx in expected_contexts if ctx not in available_contexts]
            
            if missing_contexts:
                logging.error(f"Missing required contexts: {missing_contexts}")
                return False
            
            # Validate reclassification capabilities
            if not self.financial_reclassifier.validate_configuration():
                logging.warning("Financial reclassifier configuration has issues - reclassification may be limited")
                # Continue validation as reclassification is an enhancement, not core functionality
            
            logging.info("Enhanced system integrity validation completed successfully")
            return True
            
        except Exception as e:
            logging.error(f"System integrity validation failed: {e}")
            return False