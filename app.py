import streamlit as st
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd
from io import BytesIO
import copy
import time

# Import parser modules
from bilancio_parser import BilancioParser
from excel_exporter import ExcelExporter
from configuration_manager import ConfigurationManager

# Configure page
st.set_page_config(
    page_title="FinancialLens Beta",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Modern CSS styling with red-grey palette
def inject_custom_css():
    st.markdown("""
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Root variables for consistent theming */
    :root {
        --primary-red: #E53E3E;
        --secondary-red: #FEB2B2;
        --light-red: #FED7D7;
        --primary-grey: #718096;
        --light-grey: #F7FAFC;
        --dark-grey: #2D3748;
        --success-green: #68D391;
        --warning-orange: #F6AD55;
        --border-radius: 12px;
        --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    }
    
    /* Global font */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Main container styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    
    /* Modern card styling */
    .custom-card {
        background: white;
        border-radius: var(--border-radius);
        box-shadow: var(--shadow);
        padding: 1.5rem;
        margin: 1rem 0;
        border: 1px solid #E2E8F0;
        transition: all 0.2s ease;
    }
    
    .custom-card:hover {
        box-shadow: var(--shadow-lg);
        transform: translateY(-2px);
    }
    
    /* Header styling */
    .main-header {
        text-align: center;
        margin-bottom: 2rem;
        padding: 0.8rem 0;
        background: linear-gradient(135deg, var(--light-red) 0%, var(--light-grey) 100%);
        border-radius: var(--border-radius);
        border: 1px solid var(--secondary-red);
    }
    
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        color: var(--primary-red);
        margin-bottom: 0;
        text-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Status indicators */
    .status-success {
        background: linear-gradient(135deg, #C6F6D5 0%, #9AE6B4 100%);
        color: #22543D;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.875rem;
        border: 1px solid #68D391;
    }
    
    .status-warning {
        background: linear-gradient(135deg, #FEEBC8 0%, #F6AD55 100%);
        color: #C05621;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.875rem;
        border: 1px solid #F6AD55;
    }
    
    .status-error {
        background: linear-gradient(135deg, var(--light-red) 0%, var(--secondary-red) 100%);
        color: #C53030;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.875rem;
        border: 1px solid var(--primary-red);
    }
    
    /* Document cards with selection state */
    .document-card {
        background: white;
        border-radius: var(--border-radius);
        box-shadow: var(--shadow);
        padding: 1.5rem;
        margin: 1rem;
        border-left: 4px solid var(--primary-red);
        transition: all 0.3s ease;
        cursor: pointer;
    }
    
    .document-card:hover {
        box-shadow: var(--shadow-lg);
        transform: translateY(-4px);
        border-left-width: 6px;
    }
    
    .document-card.selected {
        border-left-color: var(--primary-red);
        background: linear-gradient(135deg, #FFFAFA 0%, var(--light-red) 100%);
        box-shadow: var(--shadow-lg);
        transform: translateY(-2px);
        border-left-width: 6px;
    }
    
    /* BRSF Table styling */
    .brsf-container {
        background: white;
        border-radius: var(--border-radius);
        box-shadow: var(--shadow);
        padding: 1.5rem;
        margin: 1rem 0;
    }
    
    .brsf-section {
        margin-bottom: 2rem;
    }
    
    .brsf-header {
        background: linear-gradient(135deg, var(--primary-red) 0%, #C53030 100%);
        color: white;
        padding: 1rem;
        border-radius: var(--border-radius);
        font-weight: 600;
        text-align: center;
        font-size: 1.1rem;
        margin-bottom: 8px;
    }
    
    /* Balance sheet error styling */
    .balance-error-success {
        background: linear-gradient(135deg, #C6F6D5 0%, #9AE6B4 100%);
        color: #22543D;
        font-weight: 700;
    }
    
    .balance-error-warning {
        background: linear-gradient(135deg, #FEEBC8 0%, #F6AD55 100%);
        color: #C05621;
        font-weight: 700;
    }
    
    .balance-error-error {
        background: linear-gradient(135deg, var(--light-red) 0%, var(--secondary-red) 100%);
        color: #C53030;
        font-weight: 700;
    }
    
    /* Calculated rows styling */
    .calculated-row {
        background: linear-gradient(135deg, #4A5568 0%, #2D3748 100%) !important;
        color: white !important;
        font-weight: 700 !important;
        border-radius: 6px;
    }
    
    .calculated-row td {
        background: linear-gradient(135deg, #4A5568 0%, #2D3748 100%) !important;
        color: white !important;
        font-weight: 700 !important;
    }
    
    /* Upload area styling */
    .upload-area {
        border: 2px dashed var(--secondary-red);
        border-radius: var(--border-radius);
        padding: 4rem 3rem;
        text-align: center;
        background: linear-gradient(135deg, #FFFAFA 0%, var(--light-red) 100%);
        margin: 2rem 0;
        transition: all 0.3s ease;
        min-height: 200px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    
    .upload-area:hover {
        border-color: var(--primary-red);
        background: linear-gradient(135deg, var(--light-red) 0%, var(--secondary-red) 100%);
        transform: translateY(-4px);
        box-shadow: var(--shadow-lg);
    }
    
    .upload-area.loaded {
        border-color: var(--success-green);
        background: linear-gradient(135deg, #F0FFF4 0%, #C6F6D5 100%);
        opacity: 0.8;
    }
    
    .upload-icon {
        font-size: 3rem;
        color: var(--primary-red);
        margin-bottom: 1rem;
    }
    
    .upload-text {
        font-size: 1.2rem;
        font-weight: 600;
        color: var(--primary-red);
        margin-bottom: 0.5rem;
    }
    
    .upload-subtext {
        font-size: 0.9rem;
        color: var(--primary-grey);
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, var(--primary-red) 0%, #C53030 100%);
        color: white;
        border: none;
        border-radius: var(--border-radius);
        padding: 0.75rem 2rem;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.3s ease;
        box-shadow: var(--shadow);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-lg);
        background: linear-gradient(135deg, #C53030 0%, #A02626 100%);
    }
    
    .stButton > button[kind="secondary"] {
        background: linear-gradient(135deg, var(--primary-grey) 0%, #4A5568 100%);
        color: white;
    }
    
    .stButton > button[kind="secondary"]:hover {
        background: linear-gradient(135deg, #4A5568 0%, #2D3748 100%);
    }
    
    /* Progress bar */
    .stProgress .st-bo {
        background: linear-gradient(90deg, var(--primary-red) 0%, var(--secondary-red) 100%);
        border-radius: 10px;
    }
    
    /* Info boxes */
    .stAlert {
        border-radius: var(--border-radius);
        border: none;
        box-shadow: var(--shadow);
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background: linear-gradient(135deg, var(--light-grey) 0%, #EDF2F7 100%);
        border-radius: var(--border-radius);
        border: 1px solid #E2E8F0;
        font-weight: 600;
        color: var(--dark-grey);
    }
    
    /* Table enhancements */
    .stDataFrame {
        border-radius: var(--border-radius);
        overflow: hidden;
        box-shadow: var(--shadow);
    }
    
    /* Financial statement headers */
    .fs-section-header {
        background: linear-gradient(135deg, var(--primary-grey) 0%, #4A5568 100%);
        color: white;
        padding: 0.75rem 1rem;
        border-radius: var(--border-radius);
        font-weight: 600;
        font-size: 1.1rem;
        margin: 1.5rem 0 1rem 0;
        box-shadow: var(--shadow);
    }
    
    .fs-subsection-header {
        background: linear-gradient(135deg, var(--light-grey) 0%, #EDF2F7 100%);
        color: var(--dark-grey);
        padding: 0.5rem 1rem;
        border-radius: var(--border-radius);
        font-weight: 600;
        margin: 1rem 0 0.5rem 0;
        border-left: 4px solid var(--primary-red);
    }
    
    /* Metric styling */
    .metric-container {
        background: white;
        border-radius: var(--border-radius);
        box-shadow: var(--shadow);
        padding: 1rem;
        text-align: center;
        border: 1px solid #E2E8F0;
    }
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--primary-red);
    }
    
    .metric-label {
        font-size: 0.875rem;
        color: var(--primary-grey);
        font-weight: 500;
    }
    
    /* Animation for loading states */
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    .loading {
        animation: pulse 2s infinite;
    }
    
    /* Remove gap between header and dataframe */
    div[data-testid="stDataFrame"] {
        margin-top: 10px !important;
    }
    
    div[data-testid="stDataFrame"] > div {
        border-radius: 0 0 8px 8px !important;
        border-top: none !important;
    }
    
    /* Responsive design */
    @media (max-width: 768px) {
        .main-title {
            font-size: 2rem;
        }
        
        .document-card {
            margin: 0.5rem 0;
        }
    }
    </style>
    """, unsafe_allow_html=True)

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
    if 'selected_document' not in st.session_state:
        st.session_state.selected_document = None
    if 'uploaded_files_hash' not in st.session_state:
        st.session_state.uploaded_files_hash = None

def ensure_temp_directory():
    """Ensure temp_bilanci directory exists"""
    temp_dir = Path.cwd() / 'temp_bilanci'
    temp_dir.mkdir(exist_ok=True)
    return temp_dir

def cleanup_temp_files():
    """Clean up all files in temp_bilanci directory"""
    temp_dir = Path.cwd() / 'temp_bilanci'
    if temp_dir.exists():
        for file_path in temp_dir.glob('*'):
            try:
                if file_path.is_file():
                    file_path.unlink()
            except Exception as e:
                logging.warning(f"Could not delete {file_path}: {e}")

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
    reclassification = result.get('reclassification', {})
    if reclassification.get('success') and reclassification.get('orphan_voices_count', 0) > 0:
        return "Abbreviated with Notes"
    
    # Look for abbreviated format indicators
    sp = result.get('stato_patrimoniale', {})
    if sp:
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

def create_modern_header():
    """Create modern header"""
    st.markdown("""
    <div class="main-header">
        <div class="main-title">FinancialLens (BETA)</div>
    </div>
    """, unsafe_allow_html=True)

def create_about_section():
    """Create collapsible about section"""
    with st.expander("📋 About FinancialLens", expanded=False):
        st.markdown("""
        This tool parses **Italian standalone financial statements** in **PDF format**, extracting structured data for further analysis. It is designed for financial statements that meet all of the following technical and legal requirements:
        """)
        
        st.markdown("#### 📄 Supported Documents")
        st.markdown("""
        - **Type**: Italian Standalone (non-consolidated) annual financial statements
        - **Format**: PDF with **digitally selectable text** (not scanned images)
        - **Layout**:
          - Generated from **XBRL filings**, typically downloaded from official sources such as InfoCamere, Cerved, or Registro Imprese
          - Presented in a **classic tabular layout** with alternating row colors (usually white and light blue)
          - Each financial item appears on its own row, with:
            - a label on the left (e.g. "B. Fixed Assets", "D. Payables")
            - two numeric columns (typically current year and previous year)
            - no merged cells or embedded images
          - Structure based on **Italian Civil Code schema**
        """)
        
        st.markdown("#### 📊 Supported Filing Types")
        st.markdown("""
        This parser currently supports the following statement formats:
        - **"Bilancio sintetico"** – summary format without explanatory notes
        - **"Bilancio abbreviato"** – abbreviated format (Art. 2435-bis)
        - **"Bilancio sintetico con dettaglio in Nota Integrativa"** – summary format with receivables and payables detailed in the Notes section
        """)
        
        st.markdown("#### 🧪 Experimental Compatibility")
        st.markdown("""
        Preliminary or interim financial statements may be compatible **if** they follow the same structure and nomenclature, but they are **not officially supported or tested** yet.
        """)
        
        st.markdown("#### ❌ Unsupported Documents")
        st.markdown("""
        - Consolidated financial statements
        - Custom or reformatted layouts
        - Scanned PDFs or image-based files (no OCR support)
        - PDFs with non-standard structure, merged cells, or visual formatting anomalies
        """)
        
        st.markdown("#### ⚠️ Important Notes")
        st.markdown("""
        - This is a **BETA version**: parsing errors or inconsistencies may occur. **Manual review is strongly recommended!**
        - The parser relies on the **standard Italian XBRL taxonomy** for label recognition.
        """)

def create_upload_section():
    """Create upload section with dynamic state"""
    # Check if documents are loaded
    documents_loaded = bool(st.session_state.parsing_results)
    
    if documents_loaded:
        # Show loaded state
        loaded_files = list(st.session_state.parsing_results.keys())
        files_text = ", ".join([f.split('.')[0] for f in loaded_files[:3]])
        if len(loaded_files) > 3:
            files_text += f" and {len(loaded_files) - 3} more"
        
        st.markdown(f"""
        <div class="upload-area loaded">
            <div class="upload-icon">✅</div>
            <div class="upload-text">Documents Loaded</div>
            <div class="upload-subtext">{files_text}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Show upload prompt
        st.markdown("""
        <div class="upload-area">
            <div class="upload-icon">📁</div>
            <div class="upload-text">Upload Financial Statements</div>
            <div class="upload-subtext">Select up to 5 PDF files for analysis</div>
        </div>
        """, unsafe_allow_html=True)
    
    uploaded_files = st.file_uploader(
        "Drag and drop your PDF files here or click to browse",
        type=['pdf'],
        accept_multiple_files=True,
        help="Maximum 5 files, PDF format only"
    )
    
    return uploaded_files

def check_file_changes(uploaded_files):
    """Check if uploaded files have changed and reset state if needed"""
    current_files_hash = None
    if uploaded_files:
        current_files_hash = hash(tuple(f.name + str(f.size) for f in uploaded_files))
    
    previous_hash = st.session_state.get('uploaded_files_hash', None)
    
    if current_files_hash != previous_hash:
        # Reset all relevant session state
        st.session_state.parsing_results = {}
        st.session_state.user_modifications = {}
        st.session_state.selected_document = None
        st.session_state.view_mode = "view"
        st.session_state.uploaded_files_hash = current_files_hash
        
        # Clean up temp files when files change
        cleanup_temp_files()
        
        return True  # Files changed
    
    return False  # No change

def process_uploaded_files(uploaded_files):
    """Process uploaded PDF files with progress indicators"""
    if not uploaded_files:
        return
    
    if not setup_parser():
        return
    
    # Ensure temp directory exists and clean it
    temp_dir = ensure_temp_directory()
    cleanup_temp_files()
    
    # Clear previous results
    st.session_state.parsing_results = {}
    st.session_state.user_modifications = {}
    
    # Create progress placeholder that will be completely cleared
    progress_placeholder = st.empty()
    
    with progress_placeholder.container():
        st.markdown("### 🔄 Processing Financial Statements")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        temp_files_created = []
        
        for i, uploaded_file in enumerate(uploaded_files):
            filename = uploaded_file.name
            status_text.markdown(f"**Processing:** `{filename}`")
            
            # Save uploaded file to temp directory
            temp_file_path = temp_dir / f"{filename}_{int(time.time())}.pdf"
            temp_files_created.append(temp_file_path)
            
            try:
                # Write file to temp directory
                with open(temp_file_path, 'wb') as f:
                    f.write(uploaded_file.getvalue())
                
                # Parse the file
                result = st.session_state.parser.parse(temp_file_path)
                
                if result:
                    st.session_state.parsing_results[filename] = result
                    st.session_state.user_modifications[filename] = {}
                    status_text.markdown(f"**✅ Completed:** `{filename}`")
                else:
                    status_text.markdown(f"**❌ Failed:** `{filename}`")
                
            except Exception as e:
                st.error(f"Error processing {filename}: {str(e)}")
            
            # Update progress
            progress_bar.progress((i + 1) / len(uploaded_files))
            time.sleep(0.5)
        
        # Clean up temporary files
        for temp_file_path in temp_files_created:
            try:
                if temp_file_path.exists():
                    temp_file_path.unlink()
            except Exception as e:
                logging.warning(f"Could not delete {temp_file_path}: {e}")
        
        status_text.markdown("**🎉 Processing Complete!**")
        time.sleep(1)
    
    # Clear the progress container completely and force refresh
    progress_placeholder.empty()
    st.rerun()

def create_document_cards(successful_results):
    """Create document cards with selection indicators"""
    if not successful_results:
        return
    
    st.divider()
    st.markdown("### 📊 Analysis Results")
    st.caption("Click on a document to view detailed analysis")
    
    # Create cards in grid layout
    cols = st.columns(min(len(successful_results), 3))
    
    for idx, (filename, result) in enumerate(successful_results.items()):
        col = cols[idx % 3]
        
        with col:
            status = get_document_status(result)
            year = get_document_year(result)
            doc_type = get_document_type(result)
            
            # Check if this document is selected
            is_selected = st.session_state.selected_document == filename
            
            # Status styling
            if status == "SUCCESS":
                status_class = "status-success"
                status_icon = "✅"
            elif status == "SUCCESS_WITH_TOLERANCE":
                status_class = "status-warning"
                status_icon = "⚠️"
            else:
                status_class = "status-error"
                status_icon = "❌"
            
            # Create button with selection state
            button_style = "primary" if is_selected else "secondary"
            
            if st.button(
                f"📄 {filename[:20]}{'...' if len(filename) > 20 else ''}",
                key=f"doc_card_{idx}",
                type=button_style,
                use_container_width=True
            ):
                st.session_state.selected_document = filename
                st.rerun()
            
            # Card content with selection styling
            card_class = "selected" if is_selected else ""
            st.markdown(f"""
            <div class="document-card {card_class}" style="margin-top: -0.5rem; padding: 0.5rem; background: white; border-radius: 8px; border: 1px solid #E2E8F0;">
                <div class="{status_class}" style="display: inline-block; margin-bottom: 0.5rem;">
                    {status_icon} {status.replace('_', ' ').title()}
                </div>
                <div style="font-size: 0.875rem; color: var(--primary-grey);">
                    <strong>Year:</strong> {year}<br>
                    <strong>Type:</strong> {doc_type}
                </div>
            </div>
            """, unsafe_allow_html=True)

def get_balance_sheet_error(result: Dict[str, Any]) -> Tuple[float, str]:
    """Calculate balance sheet error and determine status color"""
    reclassification = result.get('reclassification', {})
    
    if not reclassification.get('success'):
        return 0.0, "success"
    
    balance_validation = reclassification.get('balance_sheet_validation', {})
    difference = balance_validation.get('difference', 0.0)
    status = balance_validation.get('status', 'success')
    
    # Determine color based on status
    if status == 'success':
        color_class = "balance-error-success"
    elif status == 'success_with_tolerance':
        color_class = "balance-error-warning"
    else:
        color_class = "balance-error-error"
    
    return difference, color_class

def display_brsf_table(result: Dict[str, Any], filename: str):
    """Display BRSF table with enhanced formatting"""
    # Get current data with user modifications applied
    current_result = apply_user_modifications(result, filename)
    reclassification = current_result.get('reclassification', {})
    
    if not reclassification.get('success'):
        st.warning("🔍 BRSF data not available - reclassification failed or not performed")
        return
    
    scale_factor = 1000 if st.session_state.brsf_scale == "/1000" else 1
    scale_label = " (thousands €)" if scale_factor == 1000 else " (€)"
    
    reclassified_data = reclassification.get('reclassified_data', {})
    
    # Define calculated/derived items
    calculated_items = {
        'Cost of Sales', 'GROSS PROFIT', 'S G & A', 'NET OP. PROFIT',
        'PRE TAX PROFIT', 'PROFIT AFTER TAX', 
        'Quick Assets', 'Other Current', 'TOT CURR. ASS.',
        'Financial/Other fix Ass', 'TOTAL FIX. ASS.', 'BAL. SHEET TOT',
        'Total Short Term Debt', 'TOT CURR. LIAB.',
        'Sub. Loan/Oth. LT', 'TOTAL LT LIAB', 'Liabs less net worth',
        'TOT NET WORTH'
    }
    
    # Define section structures with spacing
    section_structures = {
        'P&L': [
            'Total Sales', 'Cost of Sales', 'GROSS PROFIT', 'S G & A', 'NET OP. PROFIT',
            'Interest Received', 'Interest Paid', 'Other Income/Expense', 'PRE TAX PROFIT',
            'Taxation', 'PROFIT AFTER TAX', '', '', '', 'Deprecation'  # Three empty rows before Deprecation
        ],
        'ASSETS': [
            'Cash & Equivalent', 'Trade Debtors', 'Quick Assets', 'Stock & Work in Progr.',
            'Other Current', 'TOT CURR. ASS.', 'Tangible Fxed Assets', 'Intangibles',
            'Goodwill', 'Financial/Other fix Ass', 'TOTAL FIX. ASS.', 'BAL. SHEET TOT',
            '', '', 'Balance Sheet Err'  # Two empty rows before Balance Sheet Error
        ],
        'LIABILITIES': [
            'Overdrafts & STD', 'Current Portion LTD', 'Total Short Term Debt', 'Trade Creditors',
            'Other Current', 'TOT CURR. LIAB.', 'Total Long Term Debt', 'Provisions',
            'Sub. Loan/Oth. LT', 'TOTAL LT LIAB', 'Liabs less net worth', 'Share Holders Funds',
            "Ret'd Earnings/Resv's", 'TOT NET WORTH', 'BAL. SHEET TOT'
        ]
    }
    
    # Get balance sheet error for Assets section
    bs_error, error_color_class = get_balance_sheet_error(current_result)
    
    # Create columns for the three sections
    col1, col2, col3 = st.columns(3)
    columns = [col1, col2, col3]
    sections = ['P&L', 'ASSETS', 'LIABILITIES']
    
    for col, section in zip(columns, sections):
        with col:
            # Section header with fully rounded corners
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #E53E3E 0%, #C53030 100%);
                color: white;
                padding: 12px;
                text-align: center;
                font-weight: 600;
                font-size: 1.1rem;
                border-radius: 12px;
                margin-bottom: 0px;
            ">{section}</div>
            """, unsafe_allow_html=True)
            
            section_data = reclassified_data.get(section, {})
            section_structure = section_structures.get(section, [])
            
            # Create DataFrame
            data_rows = []
            for item in section_structure:
                if item == '':
                    # Empty row
                    data_rows.append({
                        'Item': '',
                        f'Value{scale_label}': '',
                        'IsCalculated': False,
                        'IsEmpty': True,
                        'IsBalanceError': False
                    })
                elif item == 'Balance Sheet Err':
                    # Balance sheet error row
                    scaled_error = bs_error / scale_factor if scale_factor > 1 else bs_error
                    if scale_factor == 1000:
                        formatted_error = f"{round(scaled_error):,}"
                    else:
                        formatted_error = f"{scaled_error:,.2f}"
                    
                    data_rows.append({
                        'Item': 'Balance Sheet Err',
                        f'Value{scale_label}': formatted_error,
                        'IsCalculated': False,
                        'IsEmpty': False,
                        'IsBalanceError': True,
                        'ErrorColorClass': error_color_class
                    })
                else:
                    # Regular item
                    value = section_data.get(item, 0.0)
                    scaled_value = value / scale_factor if scale_factor > 1 else value
                    
                    if scale_factor == 1000:
                        formatted_value = f"{round(scaled_value):,}"
                    else:
                        formatted_value = f"{scaled_value:,.2f}"
                    
                    data_rows.append({
                        'Item': item,
                        f'Value{scale_label}': formatted_value,
                        'IsCalculated': item in calculated_items,
                        'IsEmpty': False,
                        'IsBalanceError': False
                    })
            
            df = pd.DataFrame(data_rows)
            
            # Display without internal columns
            display_df = df[['Item', f'Value{scale_label}']].copy()
            
            # Apply styling
            def highlight_rows(row):
                styles = ['', '']
                row_index = row.name
                
                if df.loc[row_index, 'IsEmpty']:
                    # Empty row - transparent
                    empty_style = 'background-color: transparent; color: transparent; border: none;'
                    styles = [empty_style, empty_style]
                elif df.loc[row_index, 'IsBalanceError']:
                    # Balance sheet error row with color
                    error_class = df.loc[row_index, 'ErrorColorClass']
                    if error_class == 'balance-error-success':
                        error_style = 'background-color: #C6F6D5; color: #22543D; font-weight: bold;'
                    elif error_class == 'balance-error-warning':
                        error_style = 'background-color: #FEEBC8; color: #C05621; font-weight: bold;'
                    else:
                        error_style = 'background-color: #FED7D7; color: #C53030; font-weight: bold;'
                    styles = [error_style, error_style]
                elif df.loc[row_index, 'IsCalculated']:
                    # Calculated rows
                    calculated_style = 'background-color: #4A5568; color: white; font-weight: bold;'
                    styles = [calculated_style, calculated_style]
                else:
                    # Regular rows
                    regular_style = 'background-color: white; color: #2D3748;'
                    styles = [regular_style, regular_style]
                
                return styles
            
            styled_df = display_df.style.apply(highlight_rows, axis=1)
            
            # Additional table styling
            styled_df = styled_df.set_table_styles([
                {
                    'selector': 'thead th',
                    'props': [
                        ('background-color', '#F7FAFC'),
                        ('color', '#2D3748'),
                        ('font-weight', 'bold'),
                        ('text-align', 'center'),
                        ('padding', '10px'),
                        ('border', '1px solid #E2E8F0')
                    ]
                },
                {
                    'selector': 'tbody td',
                    'props': [
                        ('padding', '8px'),
                        ('border', '1px solid #E2E8F0'),
                        ('text-align', 'left')
                    ]
                },
                {
                    'selector': 'tbody td:nth-child(2)',
                    'props': [
                        ('text-align', 'right')
                    ]
                }
            ])
            
            # Display the dataframe
            st.dataframe(styled_df, use_container_width=True, hide_index=True, height=565)

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
    """Recalculate BRSF data using FinancialReclassifier with modified values"""
    try:
        from financial_reclassifier import FinancialReclassifier
        
        # Initialize the reclassifier with config path
        current_dir = Path.cwd()
        config_dir = current_dir / 'config'
        config_file = current_dir / 'config.yaml'
        
        if config_dir.exists() and any(config_dir.glob('config_*.yaml')):
            config_path = config_dir
        elif config_file.exists():
            config_path = config_file
        else:
            return modified_result
        
        # Create reclassifier instance
        reclassifier = FinancialReclassifier(config_path)
        
        # Validate reclassifier configuration
        if not reclassifier.validate_configuration():
            return modified_result
        
        # Use reclassifier to process modified data
        reclassification_result = reclassifier.reclassify_financial_data(modified_result)
        
        if reclassification_result.success:
            # Update reclassification data in result
            modified_result['reclassification'] = {
                'success': True,
                'reclassified_data': reclassification_result.reclassified_data,
                'reclassified_details': reclassification_result.reclassified_details,
                'balance_sheet_validation': reclassification_result.balance_sheet_validation,
                'orphan_voices_count': reclassification_result.orphan_voices_count
            }
        else:
            if 'reclassification' in modified_result:
                modified_result['reclassification']['success'] = False
        
        return modified_result
        
    except Exception as e:
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

def display_financial_statements(result: Dict[str, Any], filename: str):
    """Display detailed financial statements"""
    # Get current data with user modifications applied
    current_result = apply_user_modifications(result, filename)
    
    # Income Statement Section
    with st.expander("📈 **Income Statement (Conto Economico)**", expanded=False):
        ce_data = current_result.get('conto_economico', {})
        
        if st.session_state.view_mode == "edit":
            display_editable_section(ce_data, "conto_economico", filename)
        else:
            display_readonly_section(ce_data, "Income Statement")
    
    # Balance Sheet Section
    with st.expander("📊 **Balance Sheet (Stato Patrimoniale)**", expanded=False):
        sp_data = current_result.get('stato_patrimoniale', {})
        
        if st.session_state.view_mode == "edit":
            if 'attivo' in sp_data:
                st.markdown('<div class="fs-section-header">ASSETS (ATTIVO)</div>', unsafe_allow_html=True)
                display_editable_section(sp_data['attivo'], "stato_patrimoniale_attivo", filename)
            
            if 'passivo' in sp_data:
                st.markdown('<div class="fs-section-header">LIABILITIES (PASSIVO)</div>', unsafe_allow_html=True)
                display_editable_section(sp_data['passivo'], "stato_patrimoniale_passivo", filename)
        else:
            if 'attivo' in sp_data:
                st.markdown('<div class="fs-section-header">ASSETS (ATTIVO)</div>', unsafe_allow_html=True)
                display_readonly_section(sp_data['attivo'], "Assets")
            
            if 'passivo' in sp_data:
                st.markdown('<div class="fs-section-header">LIABILITIES (PASSIVO)</div>', unsafe_allow_html=True)
                display_readonly_section(sp_data['passivo'], "Liabilities")

def display_readonly_section(data: Dict[str, Any], section_name: str):
    """Display financial section in read-only mode"""
    flat_items = flatten_financial_data(data)
    
    for item in flat_items:
        # Create indentation based on level
        indent_pixels = item['level'] * 20
        name = item['voce_canonica']
        value = item['valore']
        
        # Create columns for name and value
        col1, col2 = st.columns([4, 1])
        
        with col1:
            # Apply indentation using markdown
            if indent_pixels > 0:
                st.markdown(f'<div style="margin-left: {indent_pixels}px;">{name}</div>', unsafe_allow_html=True)
            else:
                if item['level'] == 0:
                    st.markdown(f"**{name}**")
                else:
                    st.write(name)
        
        with col2:
            # Show enrichment icon for NI items
            enrichment_icon = ' 📝' if item.get('from_ni', False) or item.get('enriched_from_ni', False) else ''
            
            if item['level'] == 0:
                st.markdown(f"**{value:,.2f}{enrichment_icon}**")
            else:
                st.write(f"{value:,.2f}{enrichment_icon}")

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
        
        # Special case: Credits and Debits are never editable if they have children or are enriched
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
                    st.markdown(f"**{name}**")
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
                    
                    # Trigger immediate recalculation
                    st.rerun()
            else:
                # Non-editable, show as text with enrichment icon
                enrichment_icon = ' 📝' if item.get('enriched_from_ni', False) or item.get('from_ni', False) else ''
                
                if item['level'] == 0:
                    st.markdown(f"**{current_value:,.2f}{enrichment_icon}**")
                else:
                    st.write(f"{current_value:,.2f}{enrichment_icon}")
    
    if changes_made:
        st.info("💡 Values updated! Parent totals will be recalculated automatically.")

def generate_excel_with_modifications(result: Dict[str, Any], filename: str) -> bytes:
    """Generate Excel file with user modifications applied"""
    # Get result with modifications applied
    modified_result = apply_user_modifications(result, filename)
    
    # Generate Excel using existing exporter
    excel_buffer = BytesIO()
    
    # Create temporary file path
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
        # Clean up temporary file
        try:
            Path(tmp_file_path).unlink(missing_ok=True)
        except PermissionError:
            import time
            time.sleep(0.1)
            try:
                Path(tmp_file_path).unlink(missing_ok=True)
            except:
                pass

def create_action_buttons(selected_result, selected_filename):
    """Create action buttons for export and reset"""
    st.divider()
    st.markdown("### 📥 Export & Actions")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # Download Excel button
        if selected_result:
            try:
                excel_data = generate_excel_with_modifications(selected_result, selected_filename)
                
                st.download_button(
                    label="📊 Download Excel Report",
                    data=excel_data,
                    file_name=f"{Path(selected_filename).stem}_financiallens.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Error generating Excel file: {str(e)}")
    
    with col3:
        # Reset button
        if st.button("🔄 Reset All", type="secondary", use_container_width=True):
            st.session_state.show_reset_confirmation = True

def handle_reset_confirmation():
    """Handle the reset confirmation dialog"""
    if st.session_state.get('show_reset_confirmation', False):
        st.warning("⚠️ Are you sure you want to reset all data? This will clear all uploaded files and modifications.")
        
        col_yes, col_no = st.columns(2)
        
        with col_yes:
            if st.button("✅ Yes, Reset All", type="primary", use_container_width=True):
                # Clean up temp files first
                cleanup_temp_files()
                
                # Clear session state variables
                keys_to_reset = [
                    'uploaded_files', 'parsing_results', 'user_modifications', 
                    'current_tab', 'view_mode', 'brsf_scale', 'selected_document',
                    'show_reset_confirmation', 'uploaded_files_hash'
                ]
                
                for key in keys_to_reset:
                    if key in st.session_state:
                        del st.session_state[key]
                
                # Initialize fresh state
                init_session_state()
                
                st.success("✅ All data has been reset successfully!")
                time.sleep(1)
                st.rerun()
        
        with col_no:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.show_reset_confirmation = False
                st.rerun()

def main():
    """Main application function"""
    # Inject custom CSS
    inject_custom_css()
    
    # Initialize session state
    init_session_state()
    
    # Create modern header
    create_modern_header()
    
    # Create about section
    create_about_section()
    
    # Upload section
    uploaded_files = create_upload_section()
    
    # Validate file count
    if uploaded_files and len(uploaded_files) > 5:
        st.error("❌ Maximum 5 files allowed. Please select fewer files.")
        uploaded_files = uploaded_files[:5]
    
    # Check if files changed and reset state if needed
    files_changed = check_file_changes(uploaded_files)
    
    # Process files if uploaded and changed
    if uploaded_files and files_changed:
        st.session_state.uploaded_files = uploaded_files
        process_uploaded_files(uploaded_files)
    
    # Display results if available
    if st.session_state.parsing_results:
        
        # Get successful results
        successful_results = {
            filename: result for filename, result in st.session_state.parsing_results.items()
            if result is not None
        }
        
        if not successful_results:
            st.warning("⚠️ No financial statements were successfully processed.")
            return
        
        # Create document cards for navigation
        create_document_cards(successful_results)
        
        # Display selected document content
        if st.session_state.selected_document and st.session_state.selected_document in successful_results:
            selected_filename = st.session_state.selected_document
            selected_result = successful_results[selected_filename]
            
            # Document header
            status = get_document_status(selected_result)
            year = get_document_year(selected_result)
            doc_type = get_document_type(selected_result)
            
            # Status styling
            if status == "SUCCESS":
                status_class = "status-success"
                status_icon = "✅"
            elif status == "SUCCESS_WITH_TOLERANCE":
                status_class = "status-warning"
                status_icon = "⚠️"
            else:
                status_class = "status-error"
                status_icon = "❌"
            
            st.markdown(f"""
            <div class="custom-card">
                <h2 style="color: var(--primary-red); margin-bottom: 1rem;">📄 {selected_filename}</h2>
                <div style="display: flex; gap: 1rem; align-items: center; margin-bottom: 1rem;">
                    <div class="{status_class}">{status_icon} {status.replace('_', ' ').title()}</div>
                    <div class="metric-container" style="padding: 0.5rem 1rem;">
                        <span class="metric-label">Year:</span>
                        <span class="metric-value" style="font-size: 1rem; margin-left: 0.5rem;">{year}</span>
                    </div>
                    <div class="metric-container" style="padding: 0.5rem 1rem;">
                        <span class="metric-label">Type:</span>
                        <span class="metric-value" style="font-size: 1rem; margin-left: 0.5rem;">{doc_type}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Display validation summary
            validations = selected_result.get('validazioni', {})
            if validations:
                summary = validations.get('summary', {})
                if summary.get('messages'):
                    for message in summary['messages']:
                        st.warning(message)
            
            st.divider()
            
            # BRSF Section with its toggle
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown("### 📊 BRSF")
            
            with col2:
                scale_mode = st.toggle("📊 Show in thousands", value=(st.session_state.brsf_scale == "/1000"))
                st.session_state.brsf_scale = "/1000" if scale_mode else "actual"
            
            # BRSF Table
            display_brsf_table(selected_result, selected_filename)
            
            st.divider()
            
            # Detailed Financial Statements Section with its toggle
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown("### 📋 Detailed Financial Statements")
            
            with col2:
                edit_mode = st.toggle("✏️ Edit Mode", value=(st.session_state.view_mode == "edit"), key=f"edit_toggle_{selected_filename}")
                if edit_mode != (st.session_state.view_mode == "edit"):
                    st.session_state.view_mode = "edit" if edit_mode else "view"
                    st.rerun()
            
            # Detailed Financial Statements
            display_financial_statements(selected_result, selected_filename)
            
            # Action buttons
            create_action_buttons(selected_result, selected_filename)
        
        elif successful_results and not st.session_state.selected_document:
            # Auto-select first document if none selected
            st.session_state.selected_document = next(iter(successful_results.keys()))
            st.rerun()
    
    # Handle reset confirmation
    handle_reset_confirmation()

if __name__ == "__main__":
    main()