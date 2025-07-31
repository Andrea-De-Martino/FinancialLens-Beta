import re
import pdfplumber
import logging
from fuzzywuzzy import process, fuzz
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class NITableData:
    """Processed Nota Integrativa table data."""
    voce_canonica: str
    voce_originale: str
    valore: float
    valore_entro: float
    valore_oltre: float


@dataclass
class NIColumnMapping:
    """Column mapping for NI tables."""
    description: int
    total: int
    short_term: int
    long_term: int


class EnrichmentEngine:
    """
    Handles sophisticated Nota Integrativa processing with three-pass matching strategy.
    
    This module implements the most complex component of the financial statement
    parser system: the enrichment of abbreviated format documents using detailed
    data from the Nota Integrativa (Supplementary Notes) section. The engine
    employs a sophisticated three-pass matching strategy designed to resolve
    ambiguities and ensure accurate data integration.
    
    The enrichment process is critical for abbreviated format financial statements,
    which contain summary information in the main schema but provide detailed
    breakdowns in supplementary tables. The engine must:
    
    1. Locate and merge tables that may span multiple pages
    2. Match table rows to canonical financial statement items using multiple strategies
    3. Validate consistency between main schema and supplementary details
    4. Integrate validated data while preserving hierarchical relationships
    
    The three-pass matching strategy was developed to handle the inherent ambiguity
    in matching similar financial terms while maintaining high accuracy:
    - Pass 0: Exact pattern matching for unambiguous cases
    - Pass 1: High-confidence fuzzy matching for near-exact matches  
    - Pass 2: Flexible fuzzy matching for remaining ambiguous cases
    
    This approach prevents incorrect matches that could occur with simpler
    matching algorithms while maintaining comprehensive coverage of financial items.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize enrichment engine with processing configuration.
        
        Args:
            config: Configuration containing enrichment rules, thresholds, and column mappings
        """
        self.enrichment_rules = config.get('enrichment_rules', {})
        self.enrichment_column_keywords = config.get('enrichment_column_keywords', {})
        self.enrichment_score_threshold = config.get('enrichment_score_threshold', 85)
        self.enrichment_high_confidence_threshold = config.get('enrichment_high_confidence_threshold', 95)
        
        # Column mapping for NI tables - currently hardcoded, could be made configurable
        self.nota_integrativa_columns = config.get('nota_integrativa_columns', {
            'description': 0,
            'total': 3,
            'short_term': 4,
            'long_term': 5
        })

    def enrich_abbreviated_data(self, data_map: Dict[str, Dict], 
                               pdf: pdfplumber.PDF, 
                               start_page: int) -> Dict[str, Dict]:
        """
        Main enrichment method that processes abbreviated format documents.
        
        This method orchestrates the complete enrichment process for documents
        identified as abbreviated format. It processes each enrichment section
        (typically Crediti and Debiti) by locating relevant tables in the
        Nota Integrativa, applying the three-pass matching strategy, and
        integrating validated data into the main schema.
        
        The enrichment is applied conservatively - data is only replaced if
        validation confirms consistency between the main schema totals and
        the sum of detailed items from the Nota Integrativa. This ensures
        that enrichment enhances rather than corrupts the financial data.
        
        Args:
            data_map: Current financial data map from main schema parsing
            pdf: PDF document object for accessing Nota Integrativa pages
            start_page: Starting page number for Nota Integrativa section
            
        Returns:
            Enriched data map with detailed breakdowns where available and validated
        """
        logging.info("=== BEGIN ABBREVIATED BALANCE SHEET ENRICHMENT ===")
        logging.info(f"Nota Integrativa found starting at page {start_page + 1}")
        
        for section_name, rules in self.enrichment_rules.items():
            if section_name not in data_map:
                continue
                
            logging.info(f"\n--- Processing enrichment section: '{section_name}' ---")
            
            # Find and merge tables that may span multiple pages
            merged_table = self._find_and_merge_spanning_table(pdf, start_page, rules)
            
            if not merged_table:
                logging.warning(f"  Enrichment data not found in NI for '{section_name}'")
                continue
            
            # Apply three-pass matching strategy to extract structured data
            ni_data = self._analyze_ni_table_rows(merged_table, rules)
            if not ni_data:
                logging.warning(f"  Found table for '{section_name}' but no valid data extracted.")
                continue

            # Integrate validated data into main schema
            success = self._integrate_ni_data(data_map, section_name, ni_data)
            
            if success:
                logging.info(f"  ✅ Enrichment for '{section_name}' completed successfully.")
            else:
                logging.error(f"  ❌ Enrichment for '{section_name}' failed validation.")
        
        logging.info("=== END ENRICHMENT ===")
        return data_map

    def _find_and_merge_spanning_table(self, pdf: pdfplumber.PDF, 
                                     start_page: int, 
                                     rules: Dict[str, Any]) -> Optional[List[List[str]]]:
        """
        Find and merge tables that span multiple pages.
        
        This method preserves the exact _find_and_merge_spanning_table logic
        from the original parser. It handles the complex task of locating
        tables in the Nota Integrativa that may be split across multiple pages
        and merging them into a single coherent table for processing.
        
        The method uses title keyword matching to locate the relevant table,
        then employs header similarity detection to identify continuation
        pages. This approach handles the diverse formatting of real-world
        financial documents where tables may be split at arbitrary points.
        
        Args:
            pdf: PDF document object
            start_page: Starting page for search
            rules: Enrichment rules containing title keywords and children patterns
            
        Returns:
            Merged table data or None if not found
        """
        title_keywords = [
            self._normalize_text(t, for_matching=True) 
            for t in rules.get('titles', [])
        ]
        search_range = range(start_page, min(start_page + 20, len(pdf.pages)))
        
        for page_num in search_range:
            page = pdf.pages[page_num]
            page_text = self._normalize_text(page.extract_text() or "", for_matching=True)
            
            # Check if this page contains any of the expected title keywords
            if not any(title in page_text for title in title_keywords):
                continue
            
            logging.info(f"    Found title keywords on page {page_num + 1}")
            
            # ENHANCED: Search for tables on current page AND next page
            pages_to_check = [page_num]
            if page_num + 1 < len(pdf.pages):
                pages_to_check.append(page_num + 1)
            
            for table_page_num in pages_to_check:
                table_page = pdf.pages[table_page_num]
                tables = table_page.extract_tables()
                
                if not tables:
                    continue
                    
                for table_idx, table in enumerate(tables):
                    if not table or not table[0]:
                        continue
                    
                    # Check if table contains expected children keywords
                    table_text_for_check = self._normalize_text(
                        " ".join(str(c) for row in table for c in row if c), 
                        for_matching=True
                    )
                    if any(
                        self._normalize_text(child, for_matching=True) in table_text_for_check 
                        for child in rules.get('children', [])
                    ):
                        logging.info(
                            f"    Found candidate table at Page {table_page_num + 1}, "
                            f"Table #{table_idx + 1} (title was on page {page_num + 1}). Checking for continuation..."
                        )
                        
                        # Start with current table and look for continuations
                        merged_table = list(table)
                        current_page_idx = table_page_num
                        
                        # Look for continuation on subsequent pages
                        while current_page_idx + 1 < len(pdf.pages):
                            next_page = pdf.pages[current_page_idx + 1]
                            next_page_tables = next_page.extract_tables()
                            
                            if not next_page_tables or not next_page_tables[0]:
                                break

                            continuation_table = next_page_tables[0]
                            
                            # Check if headers are similar to determine if it's a continuation
                            if self._headers_are_similar(merged_table[0], continuation_table[0]):
                                logging.info(
                                    f"      -> Found continuation at Page {current_page_idx + 2}. "
                                    f"Merging tables."
                                )
                                merged_table.extend(continuation_table[1:])  # Skip header row
                                current_page_idx += 1
                            else:
                                break
                        
                        return merged_table
            
        return None

    def _headers_are_similar(self, header1: List[str], header2: List[str], threshold: int = 80) -> bool:
        """
        Check if two table headers are similar enough to indicate continuation.
        
        This method preserves the exact _headers_are_similar logic from the
        original parser. It uses fuzzy string matching to determine if two
        table headers are similar enough to indicate that one table is a
        continuation of another.
        
        Args:
            header1: First header row
            header2: Second header row  
            threshold: Similarity threshold (default 80)
            
        Returns:
            True if headers are similar enough to indicate continuation
        """
        if not header1 or not header2:
            return False
        
        norm_h1 = self._normalize_text(" ".join(str(c or '') for c in header1), for_matching=True)
        norm_h2 = self._normalize_text(" ".join(str(c or '') for c in header2), for_matching=True)

        return fuzz.token_set_ratio(norm_h1, norm_h2) >= threshold

    def _analyze_ni_table_rows(self, table: List[List[str]], 
                             rules: Dict[str, Any]) -> List[NITableData]:
        """
        Analyze NI table rows using three-pass matching strategy.
        
        This method preserves the exact _analyze_ni_table_rows logic with the
        sophisticated three-pass approach that was developed to resolve matching
        ambiguities. The strategy prevents incorrect matches by processing
        unambiguous cases first, then progressively handling more ambiguous
        cases with reduced datasets.
        
        The three passes are:
        1. Exact pattern matching - handles cases with specific text patterns
        2. High confidence fuzzy matching (95%+) - near-exact matches
        3. Flexible fuzzy matching (85%+) - remaining ambiguous cases
        
        Each pass removes successfully matched rules/keywords from consideration
        in subsequent passes, preventing incorrect matches and ensuring that
        each rule is used only once.
        
        Args:
            table: Raw table data from PDF
            rules: Enrichment rules containing children patterns and keywords
            
        Returns:
            List of extracted and matched financial data items
        """
        if not table or len(table) < 2:
            return []

        # Get column mapping - currently uses hardcoded mapping
        col_map = self._find_ni_columns(table[0])
        logging.info(f"    Applied column mapping: {col_map}")

        # Prepare rules structure for processing
        available_rules = rules.get('children', {}).copy()
        
        # Prepare rows for processing
        rows_to_process = []
        for row_idx, row in enumerate(table[1:]):
            if not row or len(row) <= col_map['description'] or not row[col_map['description']]:
                continue
            desc_text = str(row[col_map['description']]).replace('\n', ' ').strip()
            if not desc_text or 'totale' in desc_text.lower():
                continue
            rows_to_process.append({
                'original_row': row, 
                'desc': desc_text, 
                'idx': row_idx
            })

        extracted_data = []
        
        # --- PASS 0: EXACT PATTERN MATCHING (HIGHEST PRIORITY) ---
        logging.info("    --> Begin Pass 0: Exact Pattern Matching")
        remaining_rows_pass_1 = []
        for row_data in rows_to_process:
            norm_desc = self._normalize_text(row_data['desc'], for_matching=True)
            match_found = False
            for voce_canonica, rule_details in available_rules.items():
                for pattern in rule_details.get('patterns', []):
                    if pattern in norm_desc:
                        logging.info(
                            f"      ✓ [P0] Found exact pattern for '{row_data['desc']}' "
                            f"-> '{voce_canonica}'"
                        )
                        
                        # Remove rule to prevent reuse
                        del available_rules[voce_canonica]
                        
                        # Extract data values
                        total_val = self._safe_parse_value(row_data['original_row'], col_map['total'])
                        short_val = self._safe_parse_value(row_data['original_row'], col_map['short_term'])
                        long_val = self._safe_parse_value(row_data['original_row'], col_map['long_term'])
                        final_total = total_val if total_val != 0.0 else short_val + long_val

                        extracted_data.append(NITableData(
                            voce_canonica=voce_canonica,
                            voce_originale=row_data['desc'],
                            valore=final_total,
                            valore_entro=short_val,
                            valore_oltre=long_val
                        ))
                        match_found = True
                        break
                if match_found:
                    break
            
            if not match_found:
                remaining_rows_pass_1.append(row_data)

        # Continue only if there are remaining rows and rules
        if not remaining_rows_pass_1 or not available_rules:
            logging.info(f"    Extracted {len(extracted_data)} valid items from NI table.")
            return extracted_data

        available_keywords = list(available_rules.keys())
        rows_to_process = remaining_rows_pass_1

        # --- PASS 1: HIGH CONFIDENCE FUZZY MATCHING ---
        logging.info("    --> Begin Pass 1: High Confidence Matching (Fuzzy)")
        remaining_rows_pass_2 = []
        for row_data in rows_to_process:
            norm_desc = self._normalize_text(row_data['desc'], for_matching=True)
            best_match = process.extractOne(
                norm_desc, 
                available_keywords, 
                scorer=fuzz.ratio, 
                score_cutoff=self.enrichment_high_confidence_threshold
            )

            if best_match:
                voce_canonica, score = best_match
                logging.info(
                    f"      ✓ [P1] Found high confidence match ({score}%) for "
                    f"'{row_data['desc']}' -> '{voce_canonica}'"
                )
                available_keywords.remove(voce_canonica)
                
                total_val = self._safe_parse_value(row_data['original_row'], col_map['total'])
                short_val = self._safe_parse_value(row_data['original_row'], col_map['short_term'])
                long_val = self._safe_parse_value(row_data['original_row'], col_map['long_term'])
                final_total = total_val if total_val != 0.0 else short_val + long_val

                extracted_data.append(NITableData(
                    voce_canonica=voce_canonica,
                    voce_originale=row_data['desc'],
                    valore=final_total,
                    valore_entro=short_val,
                    valore_oltre=long_val
                ))
            else:
                remaining_rows_pass_2.append(row_data)

        # --- PASS 2: FLEXIBLE FUZZY RESOLUTION ---
        logging.info("    --> Begin Pass 2: Ambiguity Resolution (Fuzzy)")
        if remaining_rows_pass_2 and available_keywords:
            for row_data in remaining_rows_pass_2:
                norm_desc = self._normalize_text(row_data['desc'], for_matching=True)
                best_match = process.extractOne(
                    norm_desc, 
                    available_keywords, 
                    scorer=fuzz.WRatio, 
                    score_cutoff=self.enrichment_score_threshold
                )

                if best_match:
                    voce_canonica, score = best_match
                    logging.info(
                        f"      ✓ [P2] Resolved ambiguity ({score}%) for "
                        f"'{row_data['desc']}' -> '{voce_canonica}'"
                    )
                    available_keywords.remove(voce_canonica)

                    total_val = self._safe_parse_value(row_data['original_row'], col_map['total'])
                    short_val = self._safe_parse_value(row_data['original_row'], col_map['short_term'])
                    long_val = self._safe_parse_value(row_data['original_row'], col_map['long_term'])
                    final_total = total_val if total_val != 0.0 else short_val + long_val

                    extracted_data.append(NITableData(
                        voce_canonica=voce_canonica,
                        voce_originale=row_data['desc'],
                        valore=final_total,
                        valore_entro=short_val,
                        valore_oltre=long_val
                    ))
                else:
                    logging.warning(
                        f"      - [P2] No valid match found for row: '{row_data['desc']}'"
                    )

        logging.info(f"    Extracted {len(extracted_data)} valid items from NI table after three passes.")
        return extracted_data

    def _integrate_ni_data(self, data_map: Dict[str, Dict], 
                         section_name: str, 
                         ni_data: List[NITableData]) -> bool:
        """
        Integrate NI data into main data map with validation.
        
        This method preserves the exact _integrate_ni_data logic including the
        critical tolerance-based validation that ensures consistency between
        the main schema and Nota Integrativa details before replacing data.
        
        The integration process includes:
        1. Calculate totals from main schema and NI data
        2. Apply tolerance-based validation
        3. Replace main schema data only if validation passes
        4. Create detailed temporal breakdown (entro/oltre esercizio)
        5. Mark nodes as enriched to prevent recalculation
        
        Args:
            data_map: Main financial data map
            section_name: Section being enriched (e.g., 'II - Crediti')
            ni_data: Processed NI data items
            
        Returns:
            True if integration successful, False if validation failed
        """
        parent_node = data_map.get(section_name)
        if not parent_node:
            logging.error(f"    ERROR: Parent node '{section_name}' not found in data_map.")
            return False

        # Calculate schema total with fallback to temporal details
        schema_total = parent_node.get('valore', 0.0)
        if schema_total == 0.0 and '_dettaglio_scadenza' in parent_node:
            dettaglio_scadenza = parent_node.get('_dettaglio_scadenza', {})
            schema_total = dettaglio_scadenza.get('entro', 0.0) + dettaglio_scadenza.get('oltre', 0.0)
        
        ni_total = sum(item.valore for item in ni_data)
        logging.info(f"    Validation totals for '{section_name}':")
        logging.info(f"      - Main schema value: {schema_total:,.2f} €")
        logging.info(f"      - Nota Integrativa total: {ni_total:,.2f} €")

        # If the main schema has a non-zero value, validate it against the NI total.
        # If the schema value is zero, trust the NI data as it's the only source of detail.
        if schema_total > 0.0:
            tolerance = max(abs(schema_total * 0.01), 2.0)
            if abs(schema_total - ni_total) > tolerance:
                logging.error(
                    f"    VALIDATION FAILED: Discrepancy ({abs(schema_total - ni_total):,.2f}€) "
                    f"exceeds tolerance. Enrichment cancelled for '{section_name}'."
                )
                return False
        
        logging.info("    ✅ VALIDATION PASSED. Proceeding with data replacement.")

        # Clean up temporary data and replace with NI details
        if '_dettaglio_scadenza' in parent_node:
            del parent_node['_dettaglio_scadenza']
            logging.info("      - Temporary '_dettaglio_scadenza' data removed.")
        
        parent_node['valore'] = ni_total
        parent_node['dettaglio'] = {}
        
        # Create detailed breakdown for each NI item
        for item in ni_data:
            voce_canonica_dettaglio = item.voce_canonica
            dettaglio_node = {
                'voce_canonica': voce_canonica_dettaglio,
                'voce_originale': item.voce_originale,
                'valore': item.valore,
                'from_ni': True,
            }
            
            # Add temporal breakdown if present
            if item.valore_entro > 0 or item.valore_oltre > 0:
                dettaglio_scadenze = {}
                
                if item.valore_entro > 0:
                    scadenza_key_entro = f"{voce_canonica_dettaglio} esigibili entro l'esercizio successivo"
                    dettaglio_scadenze[scadenza_key_entro] = {
                        'voce_canonica': scadenza_key_entro,
                        'valore': item.valore_entro,
                        'from_ni': True
                    }

                if item.valore_oltre > 0:
                    scadenza_key_oltre = f"{voce_canonica_dettaglio} esigibili oltre l'esercizio successivo"
                    dettaglio_scadenze[scadenza_key_oltre] = {
                        'voce_canonica': scadenza_key_oltre,
                        'valore': item.valore_oltre,
                        'from_ni': True
                    }

                if dettaglio_scadenze:
                    dettaglio_node['dettaglio'] = dettaglio_scadenze

            parent_node['dettaglio'][voce_canonica_dettaglio] = dettaglio_node
        
        parent_node['enriched_from_ni'] = True
        return True

    def _find_ni_columns(self, header_row: List[str]) -> Dict[str, int]:
        """
        Map table columns to data types.
        
        This method preserves the exact _find_ni_columns logic from the original
        parser. Currently uses hardcoded column mapping but could be enhanced
        to use dynamic detection based on enrichment_column_keywords configuration.
        
        Args:
            header_row: Header row from NI table
            
        Returns:
            Dictionary mapping column types to indices
        """
        logging.info("    --> Using HARDCODED column mapping.")
        return {
            'description': self.nota_integrativa_columns['description'],
            'total': self.nota_integrativa_columns['total'],
            'short_term': self.nota_integrativa_columns['short_term'],
            'long_term': self.nota_integrativa_columns['long_term']
        }

    def _safe_parse_value(self, row: List[str], col_idx: int) -> float:
        """
        Safely parse value from table cell.
        
        Helper method that safely extracts and parses numerical values
        from table cells, handling missing or invalid data gracefully.
        
        Args:
            row: Table row data
            col_idx: Column index to parse
            
        Returns:
            Parsed float value or 0.0 if parsing fails
        """
        if col_idx == -1 or len(row) <= col_idx:
            return 0.0
        return self._parse_value(row[col_idx]) if row[col_idx] else 0.0

    def _parse_value(self, value_str: Optional[str]) -> float:
        """
        Parse value string to float exactly as original parser.
        
        Preserves the exact _parse_value logic from the original parser
        including all edge cases and formatting handling.
        
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
        
        numeric_part = re.search(r'^-?[\d.]+', clean_str)
        if not numeric_part:
            return 0.0
        
        try:
            return float(numeric_part.group(0))
        except (ValueError, TypeError):
            return 0.0

    def _normalize_text(self, text: Any, for_matching: bool = False) -> str:
        """
        Normalize text exactly as original parser.
        
        This method preserves the exact text normalization behavior
        from the original parser to ensure consistent processing.
        
        Args:
            text: Text to normalize
            for_matching: Whether to apply matching-specific normalization
            
        Returns:
            Normalized text string
        """
        if not text:
            return ""
        
        text_str = str(text).strip().lower()
        text_str = re.sub(r'[\t\r]', ' ', text_str)
        
        if for_matching:
            text_str = text_str.replace('\n', ' ')
            text_str = re.sub(r'[^a-z0-9\s]', '', text_str)
        
        return re.sub(r'\s+', ' ', text_str.strip())

    def get_enrichment_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about enrichment configuration.
        
        Returns:
            Dictionary containing enrichment statistics and configuration info
        """
        stats = {
            'total_sections': len(self.enrichment_rules),
            'sections': {}
        }
        
        for section_name, rules in self.enrichment_rules.items():
            children = rules.get('children', {})
            titles = rules.get('titles', [])
            
            stats['sections'][section_name] = {
                'children_count': len(children),
                'titles_count': len(titles),
                'has_patterns': any(
                    'patterns' in child_rules 
                    for child_rules in children.values()
                    if isinstance(child_rules, dict)
                )
            }
        
        return stats

    def validate_configuration(self) -> bool:
        """
        Validate enrichment engine configuration.
        
        Ensures that all required configuration elements are present
        and properly structured for enrichment operations.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        if not self.enrichment_rules:
            logging.error("No enrichment rules configured")
            return False
        
        for section_name, rules in self.enrichment_rules.items():
            if not isinstance(rules, dict):
                logging.error(f"Invalid rules structure for section '{section_name}'")
                return False
            
            if 'children' not in rules:
                logging.error(f"Missing 'children' in rules for section '{section_name}'")
                return False
            
            if 'titles' not in rules:
                logging.error(f"Missing 'titles' in rules for section '{section_name}'")
                return False
        
        return True