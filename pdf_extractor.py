import pdfplumber
import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SectionInfo:
    """Information about a detected document section."""
    title: str
    start_page: int
    start_position: int
    content: str


@dataclass
class TableData:
    """Structured table data with metadata."""
    page_number: int
    table_index: int
    data: List[List[str]]
    layout_info: Optional[Dict[str, Any]] = None


@dataclass
class PDFExtractionResult:
    """Complete PDF extraction results."""
    pages_text: List[str]
    tables: List[TableData]
    sections: Dict[str, SectionInfo]
    document_year: Optional[str]
    is_abbreviated_format: bool
    is_consolidated_format: bool
    ni_start_page: int

    # This separates the concept of where to STOP parsing (boundary_page)
    # from where to START enrichment (ni_start_page).
    parsing_boundary_page: int


class PDFExtractor:
    """
    Handles PDF document processing and raw data extraction.
    
    The extractor processes documents in a specific sequence:
    1. Loads the PDF and extracts raw text from all pages
    2. Detects document sections using regex patterns
    3. Identifies abbreviated format through specific text markers
    4. Extracts tables with precise settings for financial data
    5. Stops processing at a calculated boundary (e.g., Nota Integrativa or Rendiconto Finanziario)
    
    All extraction parameters and behaviors are preserved exactly as they
    were in the original parser to maintain identical processing results.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize PDF extractor with document processing configuration.
        
        Args:
            config: Configuration containing section patterns, table settings,
                and text extraction parameters
        """
        self.raw_text_sections_config = config.get('raw_text_sections', [])
        
        # Load pattern
        self.abbreviated_patterns = config.get('abbreviated_format_indicators', [])
        self.consolidated_patterns = config.get('consolidated_format_indicators', [])        

        self.table_settings = config.get('table_settings', {})
        
        section_patterns = config.get('section_patterns', {})
        self.section_titles_patterns = {
            key: re.compile(pattern, re.IGNORECASE) 
            for key, pattern in section_patterns.items()
        }
        
        # Pattern for extracting complete dates from financial documents
        self.date_patterns = {
            'dib_esercizio': re.compile(r'DIB.*?Bilancio\s+di\s+esercizio.*?al\s+(\d{1,2}[/-]\d{1,2}[/-]20\d{2})', re.IGNORECASE),
            'dib_consolidato': re.compile(r'DIB.*?Bilancio\s+consolidato.*?al\s+(\d{1,2}[/-]\d{1,2}[/-]20\d{2})', re.IGNORECASE),
            'prospetto_consolidato': re.compile(r'Prospetto.*?Bilancio.*?consolidato.*?chiuso\s+al\s+(\d{1,2}[/-]\d{1,2}[/-]20\d{2})', re.IGNORECASE),
            'bilancio_esercizio': re.compile(r'bilancio\s+di\s+esercizio\s+al\s+(\d{1,2}[/-]\d{1,2}[/-]20\d{2})', re.IGNORECASE)
        }
        self.year_pattern = re.compile(r'\b(20\d{2})\b')  # Fallback

        # Define keywords for sections that should terminate core financial statement parsing.
        # This list makes the boundary detection flexible and configurable.
        self.parsing_boundary_keywords = [
            'nota integrativa',
            'rendiconto finanziario'
        ]

    def extract_document_data(self, pdf_path: Path) -> PDFExtractionResult:
        """
        Extract all relevant data from PDF document.
        ...
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Extract sections and determine BOTH boundaries
                sections, ni_start_page, boundary_page = self._extract_sections(pdf)
                
                full_text_list = [p.extract_text(x_tolerance=1) or "" for p in pdf.pages]
                full_text_normalized = ' '.join(full_text_list).lower().replace('\n', ' ')
                is_abbreviated = self._detect_abbreviated_format(full_text_normalized)
                is_consolidated = self._detect_consolidated_format(full_text_normalized)

                # Extract tables with context until the boundary
                tables = self._extract_tables_with_context(pdf, boundary_page)
                
                document_year = self._determine_document_year(tables, full_text_list)
                
                return PDFExtractionResult(
                    pages_text=full_text_list,
                    tables=tables,
                    sections=sections,
                    document_year=document_year,
                    is_abbreviated_format=is_abbreviated,
                    is_consolidated_format=is_consolidated,
                    ni_start_page=ni_start_page,
                    parsing_boundary_page=boundary_page # Pass the new boundary page
                )
                
        except Exception as e:
            logging.error(f"Failed to extract data from PDF {pdf_path.name}: {e}")
            raise

    def _extract_sections(self, pdf: pdfplumber.PDF) -> Tuple[Dict[str, SectionInfo], int, int]:
        """
        Extract raw text sections and locate key boundary pages.
        ...
        Returns:
            Tuple of (sections dictionary, nota integrativa start page, general parsing boundary page)
        """

        raw_sections: Dict[str, SectionInfo] = {}
        section_positions: List[Dict] = []
        full_text_list = [p.extract_text(x_tolerance=1) or "" for p in pdf.pages]

        for title in self.raw_text_sections_config:
            pattern = re.compile(r'^\s*' + re.escape(title), re.IGNORECASE | re.MULTILINE)
            for page_num, page_text in enumerate(full_text_list):
                for match in pattern.finditer(page_text):
                    section_positions.append({
                        'title': title, 
                        'page': page_num, 
                        'pos': match.start()
                    })
                    break
        
        if not section_positions:
            return {}, -1, -1
        
        section_positions.sort(key=lambda x: (x['page'], x['pos']))
        unique_sections = []
        if section_positions:
            unique_sections.append(section_positions[0])
            for i in range(1, len(section_positions)):
                if section_positions[i]['title'].lower() != section_positions[i-1]['title'].lower():
                    unique_sections.append(section_positions[i])

        for i, section in enumerate(unique_sections):
            start_page, start_pos, title = section['page'], section['pos'], section['title']
            end_page = unique_sections[i+1]['page'] if i + 1 < len(unique_sections) else len(pdf.pages)
            
            content = ""
            for p_num in range(start_page, end_page):
                page_content = full_text_list[p_num]
                start = start_pos if p_num == start_page else 0
                content += page_content[start:]
            
            raw_sections[title] = SectionInfo(
                title=title,
                start_page=start_page,
                start_position=start_pos,
                content=content.strip()
            )
            
        # Find the specific Nota Integrativa start page for the Enrichment Engine
        ni_start_page = next(
            (s['page'] for s in unique_sections if 'nota integrativa' in s['title'].lower()), 
            -1
        )
        
        # Find the start pages of ALL terminating sections.
        boundary_pages = [
            s['page'] for s in unique_sections 
            if any(keyword in s['title'].lower() for keyword in self.parsing_boundary_keywords)
        ]
        
        # The true boundary is the EARLIEST of these pages.
        parsing_boundary_page = min(boundary_pages) if boundary_pages else -1

        return raw_sections, ni_start_page, parsing_boundary_page

    def _detect_abbreviated_format(self, full_text_normalized: str) -> bool:
        """
        Detect abbreviated format by requiring AT LEAST 2 of the configured patterns to be present.
        
        Uses flexible matching that ignores case, extra spaces, and punctuation
        to handle variations like "Forma Abbreviata" vs "forma abbreviata" 
        or "2435 bis" vs "2435-bis".
        
        Args:
            full_text_normalized: Normalized full text from PDF
            
        Returns:
            True if at least 2 patterns are found, False otherwise
        """
        if not self.abbreviated_patterns:
            logging.warning("No abbreviated format patterns configured")
            return False
        
        if len(self.abbreviated_patterns) < 2:
            logging.warning(f"Only {len(self.abbreviated_patterns)} pattern(s) configured, need at least 2 for 'at least 2' logic")
            # If only 1 pattern configured, ok to that
            return len(self.abbreviated_patterns) == 1 and any(
                self._normalize_for_matching(pattern) in self._normalize_for_matching(full_text_normalized)
                for pattern in self.abbreviated_patterns
            )
        
        # Check how many patterns are present
        patterns_found = []
        patterns_missing = []
        
        normalized_text = self._normalize_for_matching(full_text_normalized)
        
        for pattern in self.abbreviated_patterns:
            normalized_pattern = self._normalize_for_matching(pattern)
            
            if normalized_pattern in normalized_text:
                patterns_found.append(pattern)
                logging.info(f"✓ Found pattern: '{pattern}'")
            else:
                patterns_missing.append(pattern)
                logging.debug(f"✗ Missing pattern: '{pattern}'")
        
        # Require at least 2 patterns to be found
        required_minimum = 2
        found_count = len(patterns_found)
        
        if found_count >= required_minimum:
            logging.info(f"✅ Abbreviated format detected - found {found_count}/{len(self.abbreviated_patterns)} patterns (required: {required_minimum})")
            logging.info(f"   Matching patterns: {patterns_found}")
            return True
        else:
            logging.info(f"❌ Abbreviated format NOT detected - found only {found_count}/{len(self.abbreviated_patterns)} patterns (required: {required_minimum})")
            logging.info(f"   Found patterns: {patterns_found}")
            logging.info(f"   Missing patterns: {patterns_missing}")
            return False

    def _detect_consolidated_format(self, full_text_normalized: str) -> bool:
        """
        Detect consolidated format by requiring AT LEAST 2 of the configured patterns to be present.
        
        Uses flexible matching that ignores case, extra spaces, and punctuation
        to handle variations in consolidated format indicators.
        
        Args:
            full_text_normalized: Normalized full text from PDF
            
        Returns:
            True if at least 2 patterns are found, False otherwise
        """
        if not self.consolidated_patterns:
            logging.warning("No consolidated format patterns configured")
            return False
        
        if len(self.consolidated_patterns) < 2:
            logging.warning(f"Only {len(self.consolidated_patterns)} pattern(s) configured for consolidated detection")
            return len(self.consolidated_patterns) == 1 and any(
                self._normalize_for_matching(pattern) in self._normalize_for_matching(full_text_normalized)
                for pattern in self.consolidated_patterns
            )
        
        # Check how many patterns are present
        patterns_found = []
        patterns_missing = []
        
        normalized_text = self._normalize_for_matching(full_text_normalized)
        
        for pattern in self.consolidated_patterns:
            normalized_pattern = self._normalize_for_matching(pattern)
            
            if normalized_pattern in normalized_text:
                patterns_found.append(pattern)
                logging.info(f"✓ Found consolidated pattern: '{pattern}'")
            else:
                patterns_missing.append(pattern)
                logging.debug(f"✗ Missing consolidated pattern: '{pattern}'")
        
        # Require at least 2 patterns to be found
        required_minimum = 2
        found_count = len(patterns_found)
        
        if found_count >= required_minimum:
            logging.info(f"✅ Consolidated format detected - found {found_count}/{len(self.consolidated_patterns)} patterns (required: {required_minimum})")
            logging.info(f"   Matching patterns: {patterns_found}")
            return True
        else:
            logging.info(f"❌ Consolidated format NOT detected - found only {found_count}/{len(self.consolidated_patterns)} patterns (required: {required_minimum})")
            logging.info(f"   Found patterns: {patterns_found}")
            logging.info(f"   Missing patterns: {patterns_missing}")
            return False

    def _normalize_for_matching(self, text: str) -> str:
        """Helper method to normalize text for flexible pattern matching."""
        import re
        # Convert to lowercase, normalize spaces, remove punctuation
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)  # Remove punctuation
        text = re.sub(r'\s+', ' ', text)      # Normalize spaces
        return text.strip()

    def _extract_tables_with_context(self, pdf: pdfplumber.PDF, boundary_page: int) -> List[TableData]:
        """
        Extract tables with page context, stopping at the calculated boundary page.
        ...
        Args:
            pdf: Opened PDF document object
            boundary_page: Page number where parsing of main statements should stop.
        ...
        """
        tables = []
        
        for page_num, page in enumerate(pdf.pages):

            # Use the boundary page to stop extraction.
            if boundary_page != -1 and page_num >= boundary_page:
                break
                
            page_tables = page.extract_tables(self.table_settings) or []
            
            for table_idx, table in enumerate(page_tables):
                if not table or not table[0]:
                    continue
                    
                layout_info = self._analyze_table_layout(table, None)
                
                tables.append(TableData(
                    page_number=page_num,
                    table_index=table_idx,
                    data=table,
                    layout_info=layout_info
                ))
        
        return tables

    def _analyze_table_layout(self, table: List[List[str]], document_year: Optional[str]) -> Optional[Dict[str, Any]]:

        if not table or not table[0]:
            return None
            
        header = table[0]

        if document_year:
            year_in_header = False
            for i, h in enumerate(header):
                if h and document_year in str(h):
                    desc_col = 0 if i > 0 else 1
                    year_in_header = True
                    return {
                        'year': document_year, 
                        'value_col': i, 
                        'desc_col': desc_col
                    }
            
            if not year_in_header and len(header) > 1:
                return {
                    'year': document_year, 
                    'value_col': 1, 
                    'desc_col': 0
                }

        year_positions = []
        for i, c in enumerate(header):
            if c:
                years_found = self.year_pattern.findall(str(c))
                for y in years_found:
                    year_positions.append({'year': y, 'col': i})
        
        if not year_positions:
            if len(header) > 1:
                return {
                    'year': document_year, 
                    'value_col': 1, 
                    'desc_col': 0
                }
            return None
        
        try:
            latest_year_info = max(year_positions, key=lambda x: int(x['year']))
        except (ValueError, TypeError):
            return None
        
        desc_col = 0
        if latest_year_info['col'] == 0 and len(header) > 1:
            desc_col = 1
        
        return {
            'year': latest_year_info['year'], 
            'value_col': latest_year_info['col'], 
            'desc_col': desc_col
        }

    def _determine_document_year(self, tables: List[TableData], full_text_list: List[str]) -> Optional[str]:
        """
        Determine document year using priority-based pattern matching.
        
        Strategy:
        1. Search for specific patterns (DIB, footer) with scoring
        2. Bonus points for pattern concordance
        3. Fallback to table headers if no patterns found
        
        Returns:
            Complete date string (DD/MM/YYYY format) or None if not found
        """
        # Step 1: Extract all pattern matches with scores
        date_scores = {}
        full_text = ' '.join(full_text_list)
        
        # DIB patterns (titles in first pages) - weight: +5
        for pattern_name in ['dib_esercizio', 'dib_consolidato']:
            matches = self.date_patterns[pattern_name].findall(full_text)
            for date_str in matches:
                normalized_date = self._normalize_date_format(date_str)
                if normalized_date:
                    date_scores[normalized_date] = date_scores.get(normalized_date, 0) + 5

        # Footer patterns with repetition scoring (weight: occurrences × 3)  
        for pattern_name in ['prospetto_consolidato', 'bilancio_esercizio']:
            matches = self.date_patterns[pattern_name].findall(full_text)
            for date_str in matches:
                normalized_date = self._normalize_date_format(date_str)
                if normalized_date:
                    date_scores[normalized_date] = date_scores.get(normalized_date, 0) + 3
        
        # Step 2: Apply concordance bonus (+10 if DIB and footer match)
        dib_dates = set()
        footer_dates = set()

        # Collect DIB dates
        for pattern_name in ['dib_esercizio', 'dib_consolidato']:
            matches = self.date_patterns[pattern_name].findall(full_text)
            for date_str in matches:
                normalized = self._normalize_date_format(date_str)
                if normalized:
                    dib_dates.add(normalized)

        # Collect footer dates
        for pattern_name in ['prospetto_consolidato', 'bilancio_esercizio']:
            matches = self.date_patterns[pattern_name].findall(full_text)
            for date_str in matches:
                normalized = self._normalize_date_format(date_str)
                if normalized:
                    footer_dates.add(normalized)

        concordant_dates = dib_dates.intersection(footer_dates)
        for date in concordant_dates:
            date_scores[date] += 10

        # Step 3: Select winner or fallback to tables
        if date_scores:
            winner = max(date_scores.items(), key=lambda x: x[1])
            logging.info(f"Document date determined from patterns: {winner[0]} (score: {winner[1]})")
            return winner[0]
        
        # Step 4: Fallback to table headers (existing logic with highest year)
        for table_data in tables:
            if table_data.layout_info and table_data.layout_info.get('year'):
                return table_data.layout_info['year']
        
        # Step 5: Final fallback to text scanning (existing logic)
        for page_text in full_text_list:
            years = self.year_pattern.findall(page_text)
            if years:
                try:
                    return max(years, key=int)
                except (ValueError, TypeError):
                    continue
        
        return None

    def _normalize_date_format(self, date_str: str) -> Optional[str]:
        """
        Normalize date string to DD/MM/YYYY format.
        
        Args:
            date_str: Input date string (e.g., '31-12-2024', '31/12/2024')
            
        Returns:
            Normalized date string or None if invalid
        """
        if not date_str:
            return None
        
        # Replace separators with standard format
        normalized = re.sub(r'[-.]', '/', date_str)
        
        # Validate format DD/MM/YYYY
        if re.match(r'\d{1,2}/\d{1,2}/20\d{2}', normalized):
            return normalized
        
        return None