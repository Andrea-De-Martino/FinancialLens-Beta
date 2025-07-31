# financial_reclassifier.py

import pandas as pd
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional
from dataclasses import dataclass


@dataclass
class ReclassificationResult:
    """Result of financial statement reclassification process."""
    success: bool
    reclassified_data: Dict[str, Dict[str, float]]
    reclassified_details: Dict[str, Dict[str, str]]
    balance_sheet_validation: Dict[str, Any]
    orphan_voices_count: int


@dataclass
class BalanceSheetValidation:
    """Balance sheet equilibrium validation result."""
    status: str  # 'success', 'success_with_tolerance', 'failed'
    assets_total: float
    liabilities_total: float
    difference: float
    tolerance_used: float


class FinancialReclassifier:
    """
    Handles reclassification of Italian financial statements into international format.
    
    This module transforms parsed Italian financial statement data (Stato Patrimoniale 
    and Conto Economico) into standardized international format with P&L, Assets, and 
    Liabilities sections. The reclassification follows sophisticated mapping rules and 
    performs cascading calculations to derive key financial metrics.
    
    The reclassifier implements a complex transformation process:
    1. Loads mapping rules from Excel configuration template
    2. Flattens hierarchical financial data while preserving relationships
    3. Maps Italian accounting items to international equivalents
    4. Performs cascading calculations for derived metrics
    5. Validates balance sheet equilibrium using same tolerance logic as main parser
    6. Generates detailed calculation trails for transparency
    
    The system handles the sophisticated Italian accounting hierarchy and transforms
    it into a standardized format suitable for international financial analysis,
    maintaining mathematical integrity and providing full audit trails.
    """

    def __init__(self, config_path: Path):
        """
        Initialize financial reclassifier with mapping configuration.
        
        Args:
            config_path: Path to configuration directory containing mapping template
        """
        self.config_path = config_path
        self.mapping_file = config_path / 'mapping_template.xlsx'
        
        # Validation tolerances (same as main parser)
        self.tolerance_minimum = 2000.0  # 2,000 EUR minimum tolerance
        self.tolerance_percentage = 0.02  # 2% percentage tolerance
        
        # Load mapping rules during initialization
        self.mapping_rules = self._load_mapping_configuration()

    def reclassify_financial_data(self, financial_data: Dict[str, Any]) -> ReclassificationResult:
        """
        Reclassify complete financial statement data into international format.
        
        This method orchestrates the complete reclassification process, transforming
        Italian financial statement structure into international P&L, Assets, and
        Liabilities format. It maintains the exact same logic as the original
        implementation while providing enhanced error handling and validation.
        
        The process includes:
        1. Flattening hierarchical data structure
        2. Mapping Italian items to international equivalents
        3. Performing cascading calculations for derived metrics
        4. Validating balance sheet equilibrium
        5. Generating detailed calculation documentation
        
        Args:
            financial_data: Complete parsed financial statement data
            
        Returns:
            ReclassificationResult containing transformed data and validation results
        """
        try:
            logging.info("Starting financial statement reclassification process")
            
            # Extract and flatten financial data
            flat_data = self._flatten_financial_data(financial_data)
            
            if not flat_data:
                logging.error("No financial data available for reclassification")
                return ReclassificationResult(
                    success=False,
                    reclassified_data={},
                    reclassified_details={},
                    balance_sheet_validation={},
                    orphan_voices_count=0
                )
            
            # Perform mapping and calculate orphan voices
            mapped_totals, mapped_details, orphan_count = self._map_financial_items(flat_data)
            
            # Perform cascading calculations
            final_data, final_details = self._perform_cascading_calculations(
                mapped_totals, mapped_details, flat_data
            )
            
            # Validate balance sheet equilibrium
            balance_validation = self._validate_balance_sheet_equilibrium(final_data)
            
            logging.info("Financial statement reclassification completed successfully")
            
            return ReclassificationResult(
                success=True,
                reclassified_data=final_data,
                reclassified_details=final_details,
                balance_sheet_validation=balance_validation,
                orphan_voices_count=orphan_count
            )
            
        except Exception as e:
            logging.error(f"Reclassification process failed: {e}")
            return ReclassificationResult(
                success=False,
                reclassified_data={},
                reclassified_details={},
                balance_sheet_validation={},
                orphan_voices_count=0
            )

    def _load_mapping_configuration(self) -> Dict[str, Dict[str, Any]]:
        """
        Load mapping rules from Excel configuration template.
        
        This method preserves the exact loading logic from the original implementation,
        including the hierarchical structure building and data validation. It processes
        both Stato Patrimoniale and Conto Economico sheets to create a unified mapping
        configuration with parent-child relationships.
        
        Returns:
            Dictionary containing complete mapping rules with hierarchical structure
            
        Raises:
            FileNotFoundError: If mapping template file is not found
            ValueError: If mapping template structure is invalid
        """
        if not self.mapping_file.exists():
            raise FileNotFoundError(f"Mapping template not found: {self.mapping_file}")
        
        try:
            logging.info("Loading financial reclassification mapping rules")
            
            # Load both sheets from mapping template
            sp_df = pd.read_excel(self.mapping_file, sheet_name="Stato_Patrimoniale")
            ce_df = pd.read_excel(self.mapping_file, sheet_name="Conto_Economico")
            
            # Combine sheets and clean data
            full_df = pd.concat([sp_df, ce_df], ignore_index=True)
            full_df.columns = full_df.columns.str.strip()
            
            # Clean string columns
            for col in full_df.columns:
                if full_df[col].dtype == 'object':
                    full_df[col] = full_df[col].str.strip()
            
            # Debug: Print actual column names to identify the issue
            logging.info(f"Available columns in mapping template: {list(full_df.columns)}")
            
            # Find the correct column name (flexible matching)
            voce_canonica_col = None
            for col in full_df.columns:
                if 'voce' in col.lower() and 'canonica' in col.lower():
                    voce_canonica_col = col
                    break
            
            if not voce_canonica_col:
                raise ValueError(f"Could not find 'Voce Canonica' column. Available columns: {list(full_df.columns)}")
            
            logging.info(f"Using column '{voce_canonica_col}' as canonical voice column")
            
            # Remove invalid entries and duplicates
            full_df.dropna(subset=[voce_canonica_col], inplace=True)
            full_df.drop_duplicates(subset=[voce_canonica_col], keep='first', inplace=True)
            
            # Convert to dictionary structure
            rules = full_df.set_index(voce_canonica_col).to_dict('index')
            
            # Initialize children lists for hierarchical structure
            for voce in rules:
                rules[voce]['children'] = []
            
            # Build parent-child relationships
            for voce, details in rules.items():
                parent = details.get('Genitore Canonico')
                if parent and parent in rules:
                    rules[parent]['children'].append(voce)
            
            mapping_count = len([r for r in rules.values() 
                               if not pd.isna(r.get('Mappa a questa Voce Riclassificata (DA COMPILARE)'))])
            
            logging.info(f"Loaded {len(rules)} mapping rules with {mapping_count} active mappings")
            return rules
            
        except Exception as e:
            logging.error(f"Failed to load mapping configuration: {e}")
            raise ValueError(f"Invalid mapping template structure: {e}")

    def _flatten_financial_data(self, data: Dict[str, Any]) -> Dict[str, float]:
        """
        Flatten hierarchical financial data structure into flat dictionary.
        
        This method preserves the exact flattening logic from the original implementation,
        recursively traversing the nested financial statement structure and extracting
        all voce_canonica items with their corresponding values. The flattening process
        maintains data integrity while simplifying the structure for mapping operations.
        
        Args:
            data: Hierarchical financial statement data structure
            
        Returns:
            Flat dictionary mapping canonical voice names to their values
        """
        flat_data = {}
        
        def recursive_flatten(node: Any) -> None:
            """Recursively flatten nested financial data structure."""
            if not isinstance(node, dict):
                return
                
            # Extract canonical voice and value if present
            if 'voce_canonica' in node and 'valore' in node:
                canonical_name = node['voce_canonica']
                value = node.get('valore', 0.0)
                flat_data[canonical_name] = value
            
            # Process detail breakdown if present
            if 'dettaglio' in node and isinstance(node['dettaglio'], dict):
                for child_node in node['dettaglio'].values():
                    recursive_flatten(child_node)
            else:
                # Process any nested dictionary values
                for value in node.values():
                    if isinstance(value, dict):
                        recursive_flatten(value)
        
        # Start recursive flattening from root
        recursive_flatten(data)
        
        logging.info(f"Flattened {len(flat_data)} financial items from hierarchical structure")
        return flat_data

    def _map_financial_items(self, flat_data: Dict[str, float]) -> Tuple[Dict[str, float], Dict[str, str], int]:
        """
        Map Italian financial items to international reclassified format.
        
        This method preserves the exact mapping logic from the original implementation,
        including the sophisticated handling of parent-child relationships and orphan
        voice detection. It processes each mapping rule and applies the specified
        operations while maintaining detailed audit trails.
        
        Args:
            flat_data: Flat dictionary of financial items and values
            
        Returns:
            Tuple of (mapped totals, mapped details, orphan voices count)
        """
        # Identify orphan voices not covered by mapping rules
        mapped_voices = set(self.mapping_rules.keys())
        json_voices = set(flat_data.keys())
        orphan_voices = json_voices - mapped_voices
        
        if orphan_voices:
            logging.warning(f"Found {len(orphan_voices)} unmapped voices in financial data")
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                for orphan in sorted(orphan_voices):
                    logging.debug(f"Unmapped voice: '{orphan}' with value: {flat_data[orphan]:,.2f}")
        
        reclassified_totals = {}
        reclassified_details = {}
        
        # Process each mapping rule
        for voce, rule in self.mapping_rules.items():
            map_to = rule.get('Mappa a questa Voce Riclassificata (DA COMPILARE)')
            operation = rule.get('Operazione (+ / -) (DA COMPILARE)')
            
            # Skip rules without valid mapping target
            if pd.isna(map_to) or map_to == "NON APPLICABILE":
                continue
                
            # Skip voices not present in financial data
            if voce not in flat_data:
                continue
                
            # Skip parent voices that have children present (avoid double counting)
            if any(child in flat_data for child in rule.get('children', [])):
                continue
            
            value = flat_data.get(voce, 0.0)
            
            # Validate operation specification
            if pd.isna(operation) or str(operation).strip() not in ['+', '-']:
                if not (pd.isna(operation) and value == 0):
                    logging.warning(f"Invalid operation '{operation}' for voice '{voce}' - skipping")
                continue
            
            # Initialize reclassified category if not exists
            reclassified_totals.setdefault(map_to, 0.0)
            
            # Build detail string for audit trail
            detail_string = f"- {voce}: {value:,.2f} ({operation})"
            if map_to not in reclassified_details:
                reclassified_details[map_to] = "Operations from financial data:\n" + detail_string
            else:
                reclassified_details[map_to] += "\n" + detail_string
            
            # Apply operation to reclassified total
            if operation == '+':
                reclassified_totals[map_to] += value
            elif operation == '-':
                reclassified_totals[map_to] -= value
        
        processed_items = len(reclassified_totals)
        logging.info(f"Mapped {processed_items} financial items to reclassified format")
        
        return reclassified_totals, reclassified_details, len(orphan_voices)

    def _perform_cascading_calculations(self, mapped_totals: Dict[str, float], 
                                      mapped_details: Dict[str, str], 
                                      flat_data: Dict[str, float]) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Dict[str, str]]]:
        """
        Perform sophisticated cascading calculations for international format.
        
        This method preserves the exact cascading calculation logic from the original
        implementation, including all the complex interdependencies between P&L, Assets,
        and Liabilities sections. The calculations follow international accounting
        standards and derive key financial metrics through mathematical relationships.
        
        The cascading process includes:
        - P&L: Sales → Gross Profit → Net Operating Profit → Pre-tax Profit → After-tax Profit
        - Assets: Individual components → Quick Assets → Total Current → Total Fixed → Balance Sheet Total
        - Liabilities: Debt components → Current Liabilities → Long-term Liabilities → Net Worth → Balance Sheet Total
        
        Args:
            mapped_totals: Initial mapped totals from direct mapping
            mapped_details: Initial detail strings from direct mapping
            flat_data: Original flat financial data for special calculations
            
        Returns:
            Tuple of (final calculated data, final calculation details)
        """
        final_data = {'P&L': {}, 'ASSETS': {}, 'LIABILITIES': {}}
        final_details = {'P&L': {}, 'ASSETS': {}, 'LIABILITIES': {}}

        # === P&L (Profit & Loss) Section ===
        pnl_val = final_data['P&L']
        pnl_det = final_details['P&L']
        pnl_val.update(mapped_totals)
        pnl_det.update(mapped_details)
        
        # Cascading P&L calculations preserving original logic
        total_sales = pnl_val.get('Total Sales', 0.0)
        
        initial_gross_profit = pnl_val.get('GROSS PROFIT', 0.0)
        gross_profit_final = initial_gross_profit + total_sales
        pnl_val['GROSS PROFIT'] = gross_profit_final
        
        initial_net_op_profit = pnl_val.get('NET OP. PROFIT', 0.0)
        net_op_profit_final = initial_net_op_profit + gross_profit_final
        pnl_val['NET OP. PROFIT'] = net_op_profit_final

        # Derived calculations
        pnl_val['Cost of Sales'] = total_sales - gross_profit_final
        pnl_val['S G & A'] = gross_profit_final - net_op_profit_final
        
        pre_tax_profit_final = (net_op_profit_final + pnl_val.get('Interest Received', 0.0) - 
                                pnl_val.get('Interest Paid', 0.0) + pnl_val.get('Other Income/Expense', 0.0))
        pnl_val['PRE TAX PROFIT'] = pre_tax_profit_final
        pnl_val['PROFIT AFTER TAX'] = pre_tax_profit_final - pnl_val.get('Taxation', 0.0)

        # Special depreciation calculation from Italian items
        depreciation_items = [
            'Ammortamento delle immobilizzazioni immateriali',
            'Ammortamento delle immobilizzazioni materiali',
            'Altre svalutazioni delle immobilizzazioni',
            'Svalutazioni dei crediti e delle disponibilità liquide'
        ]
        pnl_val['Deprecation'] = sum(flat_data.get(item, 0.0) for item in depreciation_items)

        # Generate P&L calculation details
        if initial_gross_profit != 0 or total_sales != 0:
            detail_str = pnl_det.get('GROSS PROFIT', 'Operations from financial data:\n- (None)')
            detail_str += f"\n\nCascading calculation:\n= [Initial Operations] (+) [Total Sales]\n= {initial_gross_profit:,.2f} (+) {total_sales:,.2f}"
            pnl_det['GROSS PROFIT'] = detail_str
        
        pnl_det['Cost of Sales'] = f"Cascading calculation:\n= [Total Sales] (-) [GROSS PROFIT]\n= {total_sales:,.2f} (-) {gross_profit_final:,.2f}"
        pnl_det['S G & A'] = f"Cascading calculation:\n= [GROSS PROFIT] (-) [NET OP. PROFIT]\n= {gross_profit_final:,.2f} (-) {net_op_profit_final:,.2f}"

        # === ASSETS Section ===
        assets_val = final_data['ASSETS']
        assets_det = final_details['ASSETS']
        assets_val.update(mapped_totals)
        assets_det.update(mapped_details)
        
        # Cascading Assets calculations
        cash_equiv = assets_val.get('Cash & Equivalent', 0.0)
        trade_debtors = assets_val.get('Trade Debtors', 0.0)
        quick_assets_final = cash_equiv + trade_debtors
        assets_val['Quick Assets'] = quick_assets_final
        
        stock_wip = assets_val.get('Stock & Work in Progr.', 0.0)
        tot_curr_ass_final = assets_val.get('TOT CURR. ASS.', 0.0) + quick_assets_final + stock_wip
        assets_val['TOT CURR. ASS.'] = tot_curr_ass_final
        
        assets_val['Other Current'] = tot_curr_ass_final - stock_wip - quick_assets_final
        
        tangible_fixed = assets_val.get('Tangible Fxed Assets', 0.0)
        intangibles = assets_val.get('Intangibles', 0.0)
        goodwill = assets_val.get('Goodwill', 0.0)
        tot_fix_ass_final = assets_val.get('TOTAL FIX. ASS.', 0.0) + tangible_fixed + intangibles + goodwill
        assets_val['TOTAL FIX. ASS.'] = tot_fix_ass_final
        
        assets_val['Financial/Other fix Ass'] = tot_fix_ass_final - tangible_fixed - intangibles - goodwill
        assets_val['BAL. SHEET TOT'] = tot_curr_ass_final + tot_fix_ass_final

        # Generate Assets calculation details
        assets_det['Quick Assets'] = f"Cascading calculation:\n= [Cash & Equivalent] (+) [Trade Debtors]\n= {cash_equiv:,.2f} (+) {trade_debtors:,.2f}"

        # === LIABILITIES Section ===
        liab_val = final_data['LIABILITIES']
        liab_det = final_details['LIABILITIES']
        liab_val.update(mapped_totals)
        liab_det.update(mapped_details)
        
        # Cascading Liabilities calculations
        overdrafts = liab_val.get('Overdrafts & STD', 0.0)
        current_ltd = liab_val.get('Current Portion LTD', 0.0)
        total_short_term_debt_final = overdrafts + current_ltd
        liab_val['Total Short Term Debt'] = total_short_term_debt_final
        
        trade_creditors = liab_val.get('Trade Creditors', 0.0)
        tot_curr_liab_final = liab_val.get('TOT CURR. LIAB.', 0.0) + total_short_term_debt_final + trade_creditors
        liab_val['TOT CURR. LIAB.'] = tot_curr_liab_final
        
        liab_val['Other Current'] = tot_curr_liab_final - total_short_term_debt_final - trade_creditors
        
        total_ltd = liab_val.get('Total Long Term Debt', 0.0)
        provisions = liab_val.get('Provisions', 0.0)
        total_lt_liab_final = liab_val.get('TOTAL LT LIAB', 0.0) + total_ltd + provisions
        liab_val['TOTAL LT LIAB'] = total_lt_liab_final
        
        liab_val['Sub. Loan/Oth. LT'] = total_lt_liab_final - total_ltd - provisions
        liab_val['Liabs less net worth'] = tot_curr_liab_final + total_lt_liab_final
        
        sh_funds = liab_val.get('Share Holders Funds', 0.0)
        retd_earnings = liab_val.get("Ret'd Earnings/Resv's", 0.0)
        tot_net_worth_final = sh_funds + retd_earnings
        liab_val['TOT NET WORTH'] = tot_net_worth_final
        
        liab_val['BAL. SHEET TOT'] = tot_curr_liab_final + total_lt_liab_final + tot_net_worth_final

        # Generate Liabilities calculation details
        liab_det['TOT NET WORTH'] = f"Cascading calculation:\n= [Share Holders Funds] (+) [Ret'd Earnings/Resv's]\n= {sh_funds:,.2f} (+) {retd_earnings:,.2f}"

        logging.info("Cascading calculations completed for all sections")
        return final_data, final_details

    def _validate_balance_sheet_equilibrium(self, final_data: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """
        Validate balance sheet equilibrium using same tolerance logic as main parser.
        
        This method applies the exact same validation logic used in the main parser
        for balance sheet equilibrium checking. It ensures that the reclassified
        balance sheet maintains mathematical consistency with appropriate tolerance
        handling for real-world rounding differences.
        
        Args:
            final_data: Complete reclassified financial data
            
        Returns:
            Dictionary containing validation results and status
        """
        assets_total = final_data.get('ASSETS', {}).get('BAL. SHEET TOT', 0.0)
        liabilities_total = final_data.get('LIABILITIES', {}).get('BAL. SHEET TOT', 0.0)
        
        difference = abs(assets_total - liabilities_total)
        
        # Apply same tolerance logic as main parser
        if difference <= self.tolerance_minimum:
            status = 'success'
            tolerance_used = self.tolerance_minimum
        else:
            # Calculate percentage-based tolerance
            reference_value = max(assets_total, liabilities_total)
            if reference_value > 0:
                percentage_tolerance = reference_value * self.tolerance_percentage
                if difference <= percentage_tolerance:
                    status = 'success_with_tolerance'
                    tolerance_used = percentage_tolerance
                else:
                    status = 'failed'
                    tolerance_used = percentage_tolerance
            else:
                status = 'failed'
                tolerance_used = self.tolerance_minimum
        
        validation_result = {
            'status': status,
            'assets_total': round(assets_total, 2),
            'liabilities_total': round(liabilities_total, 2),
            'difference': round(difference, 2),
            'tolerance_used': round(tolerance_used, 2)
        }
        
        status_msg = status.upper().replace('_', ' ')
        logging.info(f"Balance sheet validation: {status_msg} (Difference: {difference:,.2f}€)")
        
        return validation_result

    def get_reclassification_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the reclassification configuration and capabilities.
        
        Provides analytical information about the mapping rules and configuration
        for debugging and monitoring purposes.
        
        Returns:
            Dictionary containing reclassification statistics
        """
        if not self.mapping_rules:
            return {'error': 'No mapping rules loaded'}
        
        active_mappings = [
            rule for rule in self.mapping_rules.values()
            if not pd.isna(rule.get('Mappa a questa Voce Riclassificata (DA COMPILARE)'))
        ]
        
        # Count mappings by target category
        target_categories = {}
        for rule in active_mappings:
            target = rule.get('Mappa a questa Voce Riclassificata (DA COMPILARE)')
            if target and target != "NON APPLICABILE":
                target_categories[target] = target_categories.get(target, 0) + 1
        
        return {
            'total_rules': len(self.mapping_rules),
            'active_mappings': len(active_mappings),
            'target_categories': len(target_categories),
            'most_common_targets': sorted(target_categories.items(), key=lambda x: x[1], reverse=True)[:5],
            'mapping_file': str(self.mapping_file)
        }

    def validate_configuration(self) -> bool:
        """
        Validate reclassification configuration completeness and integrity.
        
        Ensures that all required configuration elements are present and properly
        structured for reclassification operations.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check if mapping file exists
            if not self.mapping_file.exists():
                logging.error(f"Mapping template file not found: {self.mapping_file}")
                return False
            
            # Check if mapping rules were loaded successfully
            if not self.mapping_rules:
                logging.error("No mapping rules loaded from configuration")
                return False
            
            # Validate that we have active mappings
            active_mappings = [
                rule for rule in self.mapping_rules.values()
                if not pd.isna(rule.get('Mappa a questa Voce Riclassificata (DA COMPILARE)'))
                and rule.get('Mappa a questa Voce Riclassificata (DA COMPILARE)') != "NON APPLICABILE"
            ]
            
            if not active_mappings:
                logging.error("No active mapping rules found in configuration")
                return False
            
            # Check for required column structure - use flexible matching
            required_columns_patterns = [
                ('voce_canonica', ['voce', 'canonica']),
                ('mapping_target', ['mappa', 'riclassificat']),
                ('operation', ['operazione', '+', '-'])
            ]
            
            sample_rule = next(iter(self.mapping_rules.values()))
            missing_columns = []
            
            for col_name, patterns in required_columns_patterns:
                found = False
                for actual_col in sample_rule.keys():
                    if any(pattern.lower() in actual_col.lower() for pattern in patterns):
                        found = True
                        break
                if not found:
                    missing_columns.append(f"{col_name} (patterns: {patterns})")
            
            if missing_columns:
                logging.error(f"Missing required column patterns in mapping template: {missing_columns}")
                logging.error(f"Available columns: {list(sample_rule.keys())}")
                return False
            
            logging.info("Reclassification configuration validation successful")
            return True
            
        except Exception as e:
            logging.error(f"Configuration validation failed: {e}")
            return False