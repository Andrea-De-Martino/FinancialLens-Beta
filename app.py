import streamlit as st
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd
from io import BytesIO
import copy
import time

# Import existing parser modules
from bilancio_parser import BilancioParser
from excel_exporter import ExcelExporter
from configuration_manager import ConfigurationManager

# Configure page
st.set_page_config(
    page_title="FinancialLens Beta",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize session state
def init_session_state():
    """Initialize session state variables"""
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = []
    if 'parsing_results' not in st.session_state:
        st.session_state.parsing_results = {}
    if 'user_modifications' not in st.session_state:
        st.session_state.user_modifications = {}
    if 'current_tab' not in st.session_state:
        st.session_state.current_tab = 0
    if 'view_mode' not in st.session_state:
        st.session_state.view_mode = "view"
    if 'brsf_scale' not in st.session_state:
        st.session_state.brsf_scale = "/1000"
    if 'parser' not in st.session_state:
        st.session_state.parser = None
    if 'exporter' not in st.session_state:
        st.session_state.exporter = None

def setup_parser():
    """Initialize parser and exporter if not already done"""
    if st.session_state.parser is None:
        try:
            # Look for configuration
            current_dir = Path.cwd()
            config_dir = current_dir / 'config'
            config_file = current_dir / 'config.yaml'
            
            if config_dir.exists() and any(config_dir.glob('config_*.yaml')):
                config_path = config_dir
            elif config_file.exists():
                config_path = config_file
            else:
                st.error("Configuration not found. Please ensure 'config' directory or 'config.yaml' file exists.")
                return False
            
            st.session_state.parser = BilancioParser(config_path)
            st.session_state.exporter = ExcelExporter()
            return True
        except Exception as e:
            st.error(f"Failed to initialize parser: {str(e)}")
            return False
    return True

def get_document_status(result: Dict[str, Any]) -> str:
    """Get document processing status"""
    if not result:
        return "FAILED"
    
    parser_status = result.get('validazioni', {}).get('summary', {}).get('status', 'failed')
    reclassification_data = result.get('reclassification', {})
    
    if reclassification_data.get('success', False):
        balance_validation = reclassification_data.get('balance_sheet_validation', {})
        reclassify_status = balance_validation.get('status', 'success')
        
        if parser_status == 'failed' or reclassify_status == 'failed':
            return "FAILED"
        elif parser_status == 'success_with_tolerance' or reclassify_status == 'success_with_tolerance':
            return "SUCCESS_WITH_TOLERANCE"
        else:
            return "SUCCESS"
    else:
        if parser_status == 'failed':
            return "FAILED"
        elif parser_status == 'success_with_tolerance':
            return "SUCCESS_WITH_TOLERANCE"
        else:
            return "SUCCESS"

def get_document_type(result: Dict[str, Any]) -> str:
    """Determine document type"""
    if not result:
        return "Unknown"
    
    # Check if abbreviated format was detected
    metadata = result.get('metadata', {})
    
    # Check for enrichment indicators
    reclassification = result.get('reclassification', {})
    if reclassification.get('success') and reclassification.get('orphan_voices_count', 0) > 0:
        return "Abbreviated with Notes"
    
    # Look for abbreviated format indicators in the structure
    sp = result.get('stato_patrimoniale', {})
    if sp:
        # Check if we have detailed breakdowns or aggregated items
        attivo = sp.get('attivo', {})
        crediti = attivo.get('II - Crediti', {})
        if crediti and crediti.get('enriched_from_ni', False):
            return "Abbreviated with Notes"
        elif crediti and not crediti.get('dettaglio'):
            return "Abbreviated"
    
    return "Extended"

def get_document_year(result: Dict[str, Any]) -> str:
    """Get document year"""
    if not result:
        return "N/A"
    return result.get('metadata', {}).get('anno_bilancio', 'N/A')

def process_uploaded_files(uploaded_files):
    """Process uploaded PDF files"""
    if not uploaded_files:
        return
    
    if not setup_parser():
        return
    
    # Clear previous results
    st.session_state.parsing_results = {}
    st.session_state.user_modifications = {}
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, uploaded_file in enumerate(uploaded_files):
        filename = uploaded_file.name
        status_text.text(f"Processing {filename}...")
        
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = Path(tmp_file.name)
        
        try:
            # Parse the file
            result = st.session_state.parser.parse(tmp_path)
            
            if result:
                st.session_state.parsing_results[filename] = result
                st.session_state.user_modifications[filename] = {}
            
        except Exception as e:
            st.error(f"Error processing {filename}: {str(e)}")
        
        finally:
            # Clean up temporary file
            tmp_path.unlink(missing_ok=True)
        
        # Update progress
        progress_bar.progress((i + 1) / len(uploaded_files))
    
    status_text.text("Processing complete!")
    time.sleep(1)
    progress_bar.empty()
    status_text.empty()

def display_brsf_table(result: Dict[str, Any], filename: str):
    """Display BRSF (Balance Reclassified Statement Format) table"""
    
    # Get current data with user modifications applied
    current_result = apply_user_modifications(result, filename)
    reclassification = current_result.get('reclassification', {})
    
    if not reclassification.get('success'):
        st.warning("BRSF data not available - reclassification failed or not performed")
        return
    
    # Scale toggle
    scale_factor = 1000 if st.session_state.brsf_scale == "/1000" else 1
    scale_label = " (in thousands)" if scale_factor == 1000 else ""
    
    reclassified_data = reclassification.get('reclassified_data', {})
    reclassified_details = reclassification.get('reclassified_details', {})
    
    # Define calculated/derived items for special styling
    calculated_items = {
        'Cost of Sales', 'GROSS PROFIT', 'S G & A', 'NET OP. PROFIT', 
        'PRE TAX PROFIT', 'PROFIT AFTER TAX', 'Quick Assets', 'Other Current',
        'TOT CURR. ASS.', 'Financial/Other fix Ass', 'TOTAL FIX. ASS.',
        'BAL. SHEET TOT', 'Total Short Term Debt', 'TOT CURR. LIAB.',
        'Sub. Loan/Oth. LT', 'TOTAL LT LIAB', 'Liabs less net worth',
        'TOT NET WORTH'
    }
    
    # Define section structures
    section_structures = {
        'P&L': [
            'Total Sales', 'Cost of Sales', 'GROSS PROFIT', 'S G & A', 'NET OP. PROFIT',
            'Interest Received', 'Interest Paid', 'Other Income/Expense', 'PRE TAX PROFIT',
            'Taxation', 'PROFIT AFTER TAX', 'Deprecation'
        ],
        'ASSETS': [
            'Cash & Equivalent', 'Trade Debtors', 'Quick Assets', 'Stock & Work in Progr.',
            'Other Current', 'TOT CURR. ASS.', 'Tangible Fxed Assets', 'Intangibles',
            'Goodwill', 'Financial/Other fix Ass', 'TOTAL FIX. ASS.', 'BAL. SHEET TOT'
        ],
        'LIABILITIES': [
            'Overdrafts & STD', 'Current Portion LTD', 'Total Short Term Debt', 'Trade Creditors',
            'Other Current', 'TOT CURR. LIAB.', 'Total Long Term Debt', 'Provisions',
            'Sub. Loan/Oth. LT', 'TOTAL LT LIAB', 'Liabs less net worth', 'Share Holders Funds',
            "Ret'd Earnings/Resv's", 'TOT NET WORTH', 'BAL. SHEET TOT'
        ]
    }
    
    # Create columns for the three sections
    col1, col2, col3 = st.columns(3)
    
    columns = [col1, col2, col3]
    sections = ['P&L', 'ASSETS', 'LIABILITIES']
    
    for col, section in zip(columns, sections):
        with col:
            st.subheader(section)
            
            section_data = reclassified_data.get(section, {})
            section_structure = section_structures.get(section, [])
            
            # Create DataFrame for better formatting
            data_rows = []
            for item in section_structure:
                value = section_data.get(item, 0.0)
                scaled_value = value / scale_factor if scale_factor > 1 else value
                
                data_rows.append({
                    'Item': item,
                    f'Value{scale_label}': f"{scaled_value:,.2f}",
                    'Calculated': item in calculated_items
                })
            
            df = pd.DataFrame(data_rows)
            
            # Create a copy for styling that includes the Calculated column
            df_for_styling = df.copy()
            
            # Style the dataframe
            def style_calculated_rows(row):
                if row['Calculated']:
                    return ['background-color: #2c5aa0; color: white'] * len(row)
                else:
                    return [''] * len(row)
            
            # Apply styling first, then drop the Calculated column
            styled_df = df_for_styling.style.apply(style_calculated_rows, axis=1)
            
            # Display without the Calculated column
            display_df = df.drop('Calculated', axis=1)
            
            # Apply the styling to the display dataframe
            def style_calculated_rows_display(row):
                row_index = row.name
                is_calculated = df_for_styling.loc[row_index, 'Calculated']
                if is_calculated:
                    return ['background-color: #2c5aa0; color: white'] * len(row)
                else:
                    return [''] * len(row)
            
            styled_display_df = display_df.style.apply(style_calculated_rows_display, axis=1)
            st.dataframe(styled_display_df, use_container_width=True, hide_index=True, height=565)

def flatten_financial_data(data: Dict[str, Any], parent_key: str = '', level: int = 0) -> List[Dict[str, Any]]:
    """Flatten hierarchical financial data for editing"""
    items = []
    
    for key, value in data.items():
        if isinstance(value, dict) and 'voce_canonica' in value:
            item = {
                'key': key,
                'voce_canonica': value.get('voce_canonica', key),
                'voce_originale': value.get('voce_originale', ''),
                'valore': value.get('valore', 0.0),
                'level': level,
                'has_children': 'dettaglio' in value and value['dettaglio'],
                'from_ni': value.get('from_ni', False),
                'enriched_from_ni': value.get('enriched_from_ni', False),
                'parent_key': parent_key
            }
            items.append(item)
            
            # Recursively add children
            if 'dettaglio' in value and value['dettaglio']:
                children = flatten_financial_data(value['dettaglio'], key, level + 1)
                items.extend(children)
    
    return items

def rebuild_hierarchical_data(flat_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Rebuild hierarchical structure from flat items"""
    # Group items by parent
    items_by_parent = {}
    root_items = []
    
    for item in flat_items:
        parent_key = item.get('parent_key', '')
        if parent_key:
            if parent_key not in items_by_parent:
                items_by_parent[parent_key] = []
            items_by_parent[parent_key].append(item)
        else:
            root_items.append(item)
    
    def build_node(item: Dict[str, Any]) -> Dict[str, Any]:
        node = {
            'voce_canonica': item['voce_canonica'],
            'voce_originale': item['voce_originale'],
            'valore': item['valore'],
            'from_ni': item['from_ni'],
            'enriched_from_ni': item['enriched_from_ni']
        }
        
        # Add children if they exist
        children_items = items_by_parent.get(item['key'], [])
        if children_items:
            node['dettaglio'] = {}
            for child in children_items:
                node['dettaglio'][child['key']] = build_node(child)
        
        return node
    
    # Build the complete structure
    result = {}
    for item in root_items:
        result[item['key']] = build_node(item)
    
    return result

def apply_user_modifications(result: Dict[str, Any], filename: str) -> Dict[str, Any]:
    """Apply user modifications to result data"""
    if filename not in st.session_state.user_modifications:
        return result
    
    modified_result = copy.deepcopy(result)
    user_mods = st.session_state.user_modifications[filename]
    
    def update_nested_value(data_dict: Dict[str, Any], item_key: str, new_value: float):
        """Update value in nested dictionary structure"""
        for key, item in data_dict.items():
            if key == item_key and isinstance(item, dict):
                item['valore'] = new_value
                return True
            elif isinstance(item, dict) and 'dettaglio' in item:
                if update_nested_value(item['dettaglio'], item_key, new_value):
                    return True
        return False
    
    # Apply modifications to each section
    for section_key, modifications in user_mods.items():
        if section_key == "conto_economico":
            ce_data = modified_result.get('conto_economico', {})
            for item_key, new_value in modifications.items():
                update_nested_value(ce_data, item_key, new_value)
                
        elif section_key == "stato_patrimoniale_attivo":
            sp_data = modified_result.get('stato_patrimoniale', {})
            attivo_data = sp_data.get('attivo', {})
            for item_key, new_value in modifications.items():
                update_nested_value(attivo_data, item_key, new_value)
                
        elif section_key == "stato_patrimoniale_passivo":
            sp_data = modified_result.get('stato_patrimoniale', {})
            passivo_data = sp_data.get('passivo', {})
            for item_key, new_value in modifications.items():
                update_nested_value(passivo_data, item_key, new_value)
    
    # Recalculate totals after applying modifications
    recalculate_totals(modified_result)
    
    # Recalculate BRSF data with modified values
    modified_result = recalculate_brsf(modified_result)
    
    return modified_result

def recalculate_brsf(modified_result: Dict[str, Any]) -> Dict[str, Any]:
    """Recalculate BRSF data using the existing FinancialReclassifier with modified values"""
    
    try:
        # Import the financial reclassifier
        from financial_reclassifier import FinancialReclassifier
        
        # Initialize the reclassifier with the same config path used by the parser
        current_dir = Path.cwd()
        config_dir = current_dir / 'config'
        config_file = current_dir / 'config.yaml'
        
        if config_dir.exists() and any(config_dir.glob('config_*.yaml')):
            config_path = config_dir
        elif config_file.exists():
            config_path = config_file
        else:
            # If no config found, return original result
            return modified_result
        
        # Create reclassifier instance
        reclassifier = FinancialReclassifier(config_path)
        
        # Validate reclassifier configuration
        if not reclassifier.validate_configuration():
            # If reclassifier config is invalid, return original result
            return modified_result
        
        # Use the existing reclassifier to process the modified data
        reclassification_result = reclassifier.reclassify_financial_data(modified_result)
        
        if reclassification_result.success:
            # Update the reclassification data in the result
            modified_result['reclassification'] = {
                'success': True,
                'reclassified_data': reclassification_result.reclassified_data,
                'reclassified_details': reclassification_result.reclassified_details,
                'balance_sheet_validation': reclassification_result.balance_sheet_validation,
                'orphan_voices_count': reclassification_result.orphan_voices_count
            }
        else:
            # If reclassification failed, mark as such but don't break the app
            if 'reclassification' in modified_result:
                modified_result['reclassification']['success'] = False
        
        return modified_result
        
    except Exception as e:
        # If anything goes wrong with reclassification, log the error but don't break the app
        st.warning(f"BRSF recalculation failed: {str(e)}. Showing original BRSF data.")
        return modified_result

def recalculate_totals(data: Dict[str, Any]):
    """Recalculate parent totals from children"""
    def recalc_node(node):
        if isinstance(node, dict) and 'dettaglio' in node and node['dettaglio']:
            # First recalculate all children
            for child in node['dettaglio'].values():
                recalc_node(child)
            
            # Don't recalculate if enriched from NI
            if not node.get('enriched_from_ni', False):
                # Calculate sum of children
                children_sum = sum(
                    child.get('valore', 0.0) 
                    for child in node['dettaglio'].values()
                    if isinstance(child, dict)
                )
                
                # Update parent value
                if children_sum != 0 or node.get('valore', 0.0) == 0:
                    node['valore'] = children_sum
    
    # Recalculate for each top-level section
    for section_data in data.values():
        if isinstance(section_data, dict):
            for item in section_data.values():
                recalc_node(item)
    """Recalculate parent totals from children"""
    def recalc_node(node):
        if isinstance(node, dict) and 'dettaglio' in node and node['dettaglio']:
            # First recalculate all children
            for child in node['dettaglio'].values():
                recalc_node(child)
            
            # Don't recalculate if enriched from NI
            if not node.get('enriched_from_ni', False):
                # Calculate sum of children
                children_sum = sum(
                    child.get('valore', 0.0) 
                    for child in node['dettaglio'].values()
                    if isinstance(child, dict)
                )
                
                # Update parent value
                if children_sum != 0 or node.get('valore', 0.0) == 0:
                    node['valore'] = children_sum
    
    # Recalculate for each top-level section
    for section_data in data.values():
        if isinstance(section_data, dict):
            for item in section_data.values():
                recalc_node(item)

def display_financial_statements(result: Dict[str, Any], filename: str):
    """Display detailed financial statements with view/edit modes"""
    
    # View/Edit mode toggle
    edit_mode = st.toggle("Edit Mode", value=(st.session_state.view_mode == "edit"), key=f"edit_toggle_{filename}")
    
    if edit_mode != (st.session_state.view_mode == "edit"):
        st.session_state.view_mode = "edit" if edit_mode else "view"
        st.rerun()
    
    # Get current data with user modifications applied
    current_result = apply_user_modifications(result, filename)
    
    # Income Statement Section
    with st.expander("📈 Income Statement (Conto Economico)", expanded=False):
        ce_data = current_result.get('conto_economico', {})
        
        if edit_mode:
            display_editable_section(ce_data, "conto_economico", filename)
        else:
            display_readonly_section(ce_data, "Income Statement")
    
    # Balance Sheet Section
    with st.expander("📊 Balance Sheet (Stato Patrimoniale)", expanded=False):
        sp_data = current_result.get('stato_patrimoniale', {})
        
        if edit_mode:
            if 'attivo' in sp_data:
                st.write("**ASSETS (ATTIVO)**")
                display_editable_section(sp_data['attivo'], "stato_patrimoniale_attivo", filename)
            
            if 'passivo' in sp_data:
                st.write("**LIABILITIES (PASSIVO)**")
                display_editable_section(sp_data['passivo'], "stato_patrimoniale_passivo", filename)
        else:
            if 'attivo' in sp_data:
                st.write("**ASSETS (ATTIVO)**")
                display_readonly_section(sp_data['attivo'], "Assets")
            
            if 'passivo' in sp_data:
                st.write("**LIABILITIES (PASSIVO)**")
                display_readonly_section(sp_data['passivo'], "Liabilities")

def display_readonly_section(data: Dict[str, Any], section_name: str):
    """Display financial section in read-only mode"""
    flat_items = flatten_financial_data(data)
    
    for item in flat_items:
        # Create indentation based on level
        indent = "　" * item['level']  # Using full-width space for better alignment
        name = f"{indent}{item['voce_canonica']}"
        value = item['valore']
        
        # Create columns for name and value
        col1, col2 = st.columns([4, 1])
        
        with col1:
            if item['level'] == 0:
                st.write(f"**{name}**")
            else:
                st.write(name)
        
        with col2:
            if item['level'] == 0:
                st.write(f"**{value:,.2f}**")
            else:
                st.write(f"{value:,.2f}")

def display_editable_section(data: Dict[str, Any], section_key: str, filename: str):
    """Display financial section in editable mode"""
    flat_items = flatten_financial_data(data)
    
    # Initialize modifications dictionary for this section if not exists
    if filename not in st.session_state.user_modifications:
        st.session_state.user_modifications[filename] = {}
    
    changes_made = False
    
    for i, item in enumerate(flat_items):
        # Create indentation based on level
        indent_pixels = item['level'] * 20
        name = item['voce_canonica']
        current_value = item['valore']
        
        # Check if this should be editable
        is_editable = not item['has_children'] and not item['enriched_from_ni']
        
        # Special case: Credits and Debits are never editable (always have temporal breakdown)
        if item['key'] in ['II - Crediti', 'D) Debiti']:
            is_editable = False
        
        # Create columns for name and value
        col1, col2 = st.columns([4, 1])
        
        with col1:
            # Apply indentation using markdown
            if indent_pixels > 0:
                st.markdown(f'<div style="margin-left: {indent_pixels}px;">{name}</div>', unsafe_allow_html=True)
            else:
                if item['level'] == 0:
                    st.write(f"**{name}**")
                else:
                    st.write(name)
        
        with col2:
            if is_editable:
                # Create unique key for this input
                input_key = f"{filename}_{section_key}_{item['key']}_{i}"
                
                new_value = st.number_input(
                    "",
                    value=float(current_value),
                    format="%.2f",
                    key=input_key,
                    label_visibility="collapsed"
                )
                
                # Check if value changed
                if new_value != current_value:
                    changes_made = True
                    # Store the change
                    if section_key not in st.session_state.user_modifications[filename]:
                        st.session_state.user_modifications[filename][section_key] = {}
                    st.session_state.user_modifications[filename][section_key][item['key']] = new_value
                    
                    # Trigger immediate recalculation and update
                    st.rerun()
            else:
                # Non-editable, show as text
                if item['level'] == 0:
                    st.write(f"**{current_value:,.2f}**")
                else:
                    st.write(f"{current_value:,.2f} {'📝' if item['enriched_from_ni'] else ''}")
    
    if changes_made:
        st.info("💡 Values updated! Parent totals will be recalculated automatically.")

def generate_excel_with_modifications(result: Dict[str, Any], filename: str) -> bytes:
    """Generate Excel file with user modifications applied"""
    # Get result with modifications applied
    modified_result = apply_user_modifications(result, filename)
    
    # Generate Excel using existing exporter with BytesIO
    excel_buffer = BytesIO()
    
    # Create temporary file path but don't keep it open
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
        tmp_file_path = tmp_file.name
    
    try:
        # Export to temporary file
        st.session_state.exporter.export(modified_result, tmp_file_path)
        
        # Read the file content into memory
        with open(tmp_file_path, 'rb') as f:
            excel_data = f.read()
        
        return excel_data
        
    finally:
        # Clean up temporary file with retry mechanism
        try:
            Path(tmp_file_path).unlink(missing_ok=True)
        except PermissionError:
            # If file is still locked, try again after a short delay
            import time
            time.sleep(0.1)
            try:
                Path(tmp_file_path).unlink(missing_ok=True)
            except:
                # If still can't delete, log but don't fail
                pass

def main():
    """Main application function"""
    init_session_state()
    
    # Fixed header
    st.title("🔍 FinancialLens Beta")
    
    # Information banner placeholder
    st.info("""
    **Professional Italian Financial Statement Analysis Tool**
    
    Insert Intro
    
    **Key Features:**
    • Insert Features
    
    **Supported Documents:** Insert Documents
    """)
    
    # Upload section
    st.subheader("📁 Upload Financial Statements")
    
    uploaded_files = st.file_uploader(
        "Select PDF files to analyze",
        type=['pdf'],
        accept_multiple_files=True,
        help="Maximum 5 files, PDF format only"
    )
    
    # Validate file count
    if uploaded_files and len(uploaded_files) > 5:
        st.error("Maximum 5 files allowed. Please select fewer files.")
        uploaded_files = uploaded_files[:5]
    
    # Process files if uploaded
    if uploaded_files and uploaded_files != st.session_state.uploaded_files:
        st.session_state.uploaded_files = uploaded_files
        process_uploaded_files(uploaded_files)
    
    # Display results if available
    if st.session_state.parsing_results:
        
        # BRSF Scale toggle
        col1, col2 = st.columns([3, 1])
        with col2:
            scale_mode = st.toggle("Show in thousands (/1000)", value=(st.session_state.brsf_scale == "/1000"))
            st.session_state.brsf_scale = "/1000" if scale_mode else "actual"
        
        # Get successful results for tabs
        successful_results = {
            filename: result for filename, result in st.session_state.parsing_results.items()
            if result is not None
        }
        
        if not successful_results:
            st.warning("No financial statements were successfully processed.")
            return
        
        # Tab system for multiple files
        if len(successful_results) > 1:
            tab_labels = []
            for filename, result in successful_results.items():
                status = get_document_status(result)
                year = get_document_year(result)
                doc_type = get_document_type(result)
                
                # Create colored status indicator
                status_color = "🟢" if status == "SUCCESS" else "🟡" if status == "SUCCESS_WITH_TOLERANCE" else "🔴"
                tab_labels.append(f"{status_color} {filename} - {year} - {doc_type}")
            
            tabs = st.tabs(tab_labels)
            
            for tab, (filename, result) in zip(tabs, successful_results.items()):
                with tab:
                    display_document_content(result, filename)
        
        else:
            # Single document - display directly
            filename, result = next(iter(successful_results.items()))
            display_document_content(result, filename)
        
        # Action buttons
        st.subheader("📥 Export & Actions")
        
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            # Download Excel button
            if successful_results:
                # For simplicity, download the first successful result
                # In a full implementation, this would be the currently selected tab
                filename, result = next(iter(successful_results.items()))
                
                try:
                    excel_data = generate_excel_with_modifications(result, filename)
                    
                    st.download_button(
                        label="📊 Download Excel Report",
                        data=excel_data,
                        file_name=f"{Path(filename).stem}_financiallens.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                except Exception as e:
                    st.error(f"Error generating Excel file: {str(e)}")
        
        with col3:
            # Reset button
            if st.button("🔄 Reset All", type="secondary"):
                # Confirmation dialog
                st.session_state.show_reset_confirmation = True
        
        # Show confirmation dialog if requested
        if st.session_state.get('show_reset_confirmation', False):
            st.warning("⚠️ Are you sure you want to reset all data? This will clear all uploaded files and modifications.")
            col_yes, col_no = st.columns(2)
            
            with col_yes:
                if st.button("✅ Yes, Reset All", type="primary"):
                    # Clear session state
                    st.session_state.uploaded_files = []
                    st.session_state.parsing_results = {}
                    st.session_state.user_modifications = {}
                    st.session_state.current_tab = 0
                    st.session_state.view_mode = "view"
                    st.session_state.show_reset_confirmation = False
                    st.rerun()
            
            with col_no:
                if st.button("❌ Cancel"):
                    st.session_state.show_reset_confirmation = False
                    st.rerun()

def display_document_content(result: Dict[str, Any], filename: str):
    """Display content for a single document"""
    
    # Document info
    status = get_document_status(result)
    year = get_document_year(result)
    doc_type = get_document_type(result)
    
    # Status indicator
    status_color = "success" if status == "SUCCESS" else "warning" if status == "SUCCESS_WITH_TOLERANCE" else "error"
    status_text = status.replace("_", " ").title()
    
    st.markdown(f"**Status:** :{status_color}[{status_text}] | **Year:** {year} | **Type:** {doc_type}")
    
    # Display validation summary
    validations = result.get('validazioni', {})
    if validations:
        summary = validations.get('summary', {})
        if summary.get('messages'):
            for message in summary['messages']:
                st.warning(message)
    
    # BRSF Table (default view)
    st.subheader("📊 BRSF - Balance Reclassified Statement Format")
    display_brsf_table(result, filename)
    
    st.divider()
    
    # Detailed Financial Statements
    st.subheader("📋 Detailed Financial Statements")
    display_financial_statements(result, filename)

if __name__ == "__main__":
    main()