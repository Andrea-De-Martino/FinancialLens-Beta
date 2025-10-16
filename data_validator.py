import logging
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    status: str  # 'success', 'success_with_tolerance', 'failed'
    reference_value: float
    compared_value: float
    difference: float
    tolerance_used: float


@dataclass
class ValidationSummary:
    """Complete validation summary for financial statement."""
    status: str
    messages: List[str]
    attivo_vs_passivo: Optional[ValidationResult]
    coerenza_utile_esercizio: Optional[ValidationResult]


class DataValidator:
    """
    Handles mathematical validations and tolerance calculations for financial statements.
    
    This module encapsulates all validation logic that ensures the mathematical
    consistency and integrity of parsed financial statement data. It performs
    the critical business validations that determine whether extracted data
    represents a valid and internally consistent financial statement.
    
    The validator performs two primary types of checks:
    1. Balance Sheet Equilibrium: Ensures total assets equal total liabilities
    2. Profit Consistency: Verifies profit figures match between Income Statement and Balance Sheet
    
    All validation calculations use precise mathematical formulas with tolerance
    handling to account for minor rounding differences that may occur in
    real-world financial documents while still detecting meaningful discrepancies.
    
    The validation status determines the overall quality assessment of the
    parsing process and influences output file naming and quality indicators.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize validator with tolerance configuration.
        
        Args:
            config: Configuration containing validation tolerance parameters
        """
        # Extract tolerance settings from config with defaults matching original
        validation_config = config.get('validation_settings', {})
        self.tolerance_percentage = validation_config.get('tolerance_percentage', 0.01)
        self.tolerance_minimum = validation_config.get('tolerance_minimum', 2.0)
        self.immediate_success_threshold = validation_config.get('immediate_success_threshold', 2.0)

    def perform_validations(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform all financial data validations.
        
        This method orchestrates the complete validation process, including
        recursive total recalculation and all consistency checks. It maintains
        the exact same validation logic and sequence as the original parser
        to ensure identical validation results and status determination.
        
        The method first recalculates parent totals from children (except for
        nodes enriched from Nota Integrativa), then performs mathematical
        validations to check internal consistency of the financial statement.
        
        Args:
            data: Complete financial statement data structure
            
        Returns:
            Validation results dictionary with detailed status information
        """
        # Perform recursive total recalculation exactly as original
        self._recursive_recalculate_totals(data)
        
        validations: Dict[str, Any] = {
            "summary": {
                "status": "success", 
                "messages": []
            }
        }
        checks_failed = False
        
        # Extract balance sheet data
        sp = data.get('stato_patrimoniale', {})

        # Calculate total attivo and passivo with recursive summation to capture all items
        tot_attivo = self._calculate_section_total(sp.get('attivo', {}))
        tot_passivo = self._calculate_section_total(sp.get('passivo', {}))
        
        # Validate balance sheet equilibrium
        if tot_attivo > 0 or tot_passivo > 0:
            status, diff = self._check_tolerance(tot_attivo, tot_passivo, tot_attivo)
            validations['attivo_vs_passivo'] = {
                "status": status, 
                "totale_attivo": round(tot_attivo, 2), 
                "totale_passivo": round(tot_passivo, 2), 
                "discrepanza": round(diff, 2)
            }
            if status == 'failed':
                checks_failed = True
        else:
            validations["summary"]["messages"].append("VALIDATION FAILED: Balance Sheet data missing.")
            checks_failed = True

        # Validate profit consistency between Income Statement and Balance Sheet
        try:
            # Check if this is a consolidated financial statement
            is_consolidated = data.get('metadata', {}).get('is_consolidated_format', False)
            
            # Find profit in Income Statement
            # For consolidated: try consolidated-specific labels first, then fallback to standard
            utile_ce_node = None
            if is_consolidated:
                # Try consolidated-specific labels
                consolidated_labels = [
                    "Utile (perdita) consolidati dell'esercizio",
                    "21) Utile (perdita) consolidati dell'esercizio",
                    "Utile consolidato dell'esercizio",
                    "Perdita consolidata dell'esercizio"
                ]
                for label in consolidated_labels:
                    utile_ce_node = self._find_item_in_structure(data.get('conto_economico', {}), label)
                    if utile_ce_node:
                        break
            
            # Fallback to standard label if not found or not consolidated
            if not utile_ce_node:
                utile_ce_node = self._find_item_in_structure(
                    data.get('conto_economico', {}), 
                    "Utile (perdita) dell'esercizio"
                )
            
            utile_ce_node = utile_ce_node or {}
            
            # Find profit in Balance Sheet
            utile_sp_node = self._find_item_in_structure(
                sp, 
                "IX - Utile (perdita) dell'esercizio"
            ) or {}
            
            val_ce = utile_ce_node.get('valore')
            val_sp = utile_sp_node.get('valore')

            if val_ce is not None and val_sp is not None:
                # For consolidated statements, add "Utile (perdita) di terzi" to Balance Sheet profit
                if is_consolidated:
                    utile_terzi_node = self._find_item_in_structure(sp, "Utile (perdita) di terzi") or {}
                    val_terzi = utile_terzi_node.get('valore', 0.0)
                    
                    if val_terzi != 0.0:
                        val_sp_consolidated = val_sp + val_terzi
                        logging.info(
                            f"Consolidated format detected: Adding minority interest "
                            f"({val_terzi:,.2f}) to Balance Sheet profit for validation"
                        )
                    else:
                        val_sp_consolidated = val_sp
                else:
                    val_sp_consolidated = val_sp
                
                status, diff = self._check_tolerance(val_ce, val_sp_consolidated, val_ce)
                
                validation_result = {
                    "status": status, 
                    "utile_conto_economico": round(val_ce, 2), 
                    "utile_stato_patrimoniale": round(val_sp, 2), 
                    "discrepanza": round(diff, 2)
                }
                
                # Add minority interest info for consolidated statements
                if is_consolidated and val_terzi != 0.0:
                    validation_result["utile_di_terzi"] = round(val_terzi, 2)
                    validation_result["utile_stato_patrimoniale_totale"] = round(val_sp_consolidated, 2)
                
                validations['coerenza_utile_esercizio'] = validation_result
                
                if status == 'failed':
                    checks_failed = True
            else:
                checks_failed = True
        except (AttributeError, KeyError):
            checks_failed = True

        # Determine overall validation status exactly as original
        if checks_failed:
            validations["summary"]["status"] = "failed"
        elif any(
            v.get('status') == 'success_with_tolerance' 
            for v in validations.values() 
            if isinstance(v, dict) and 'status' in v
        ):
            validations["summary"]["status"] = "success_with_tolerance"
            
        return validations

    def _check_tolerance(self, val1: float, val2: float, ref_val: float) -> Tuple[str, float]:
        """
        Check if difference between values is within acceptable tolerance.
        
        This method implements the exact tolerance checking logic from the
        original parser, including all edge cases and special handling for
        zero reference values. The tolerance calculation uses a sophisticated
        formula that accounts for both absolute and percentage-based thresholds.
        
        The three-tier status system provides nuanced quality assessment:
        - 'success': Values are effectively identical
        - 'success_with_tolerance': Values differ but within acceptable range
        - 'failed': Values differ beyond acceptable tolerance
        
        Args:
            val1: First value to compare
            val2: Second value to compare  
            ref_val: Reference value for percentage-based tolerance calculation
            
        Returns:
            Tuple of (validation status, absolute difference)
        """
        diff = abs(val1 - val2)
        
        # Handle zero reference value case exactly as original
        if ref_val == 0:
            if diff > self.tolerance_minimum:
                return "failed", diff
            else:
                return "success", diff
        
        # Calculate tolerance using exact same formula as original
        tolerance = max(abs(ref_val * self.tolerance_percentage), self.tolerance_minimum)
        
        # Apply tolerance checks in exact same order as original
        if diff <= self.immediate_success_threshold:
            return "success", diff
        elif diff <= tolerance:
            return "success_with_tolerance", diff
        else:
            return "failed", diff

    def _calculate_section_total(self, section: Dict[str, Any]) -> float:
        """
        Calculate total for a balance sheet section including all top-level items.
        
        Sums all first-level items directly, as their values should already represent
        the correct totals (either leaf values or calculated parent totals from children).
        
        Args:
            section: Balance sheet section dictionary (attivo or passivo)
            
        Returns:
            Total value of all first-level items
        """

        total = 0.0
        for key, item in section.items():
            if isinstance(item, dict):
                # Skip "Patrimonio netto di terzi" - already included in "A) Patrimonio netto"
                if key == 'Patrimonio netto di terzi':
                    continue
                total += item.get('valore', 0.0)
        return total

    def _recursive_recalculate_totals(self, data: Dict[str, Any]) -> None:
        """
        Recursively recalculate parent totals from children values.
        
        This method applies special calculation rules for specific financial
        statement items while maintaining the standard summation for others.
        Nodes enriched from Nota Integrativa are not recalculated since they
        contain authoritative values from supplementary documentation.
        
        The recalculation ensures that parent node values accurately reflect
        the sum of their children (or special formulas where applicable), which
        is essential for proper validation of hierarchical financial statement structures.
        
        Args:
            data: Financial statement data structure to process
        """
        # Process Balance Sheet sections with parent context
        sp = data.get('stato_patrimoniale', {})
        if sp:
            if 'attivo' in sp:
                self._recursive_recalculate_node(sp['attivo'], sp)
            if 'passivo' in sp:
                # Pass the passivo node itself as parent for Patrimonio netto special case
                self._recursive_recalculate_node(sp['passivo'], sp['passivo'])

        # Process Income Statement with parent context
        ce = data.get('conto_economico', {})
        if ce:
            self._recursive_recalculate_node(ce, ce)

    def _recursive_recalculate_node(self, node: Any, parent_node: Any = None) -> None:
        """
        Recursively recalculate totals for a single node and its children.
        
        This helper method implements the core recursive calculation logic,
        including special calculation rules for specific financial statement items
        that require custom formulas instead of simple summation.
        
        Special calculation rules are applied for:
        - C) Proventi e oneri finanziari: 15+16-17±17bis
        - Imposte sul reddito: sum all except subtract consolidato fiscale
        - D) Rettifiche di valore: Rivalutazioni - Svalutazioni  
        - A) Patrimonio netto: includes Patrimonio netto di terzi
        
        Args:
            node: Node to process (can be dict or other type)
            parent_node: Parent node (used for special cases like Patrimonio netto)
        """
        if not isinstance(node, dict):
            return
            
        for canonical_name, item in node.items():
            if isinstance(item, dict) and 'dettaglio' in item and item.get('dettaglio'):
                # Skip recalculation if enriched from Nota Integrativa
                if not item.get('enriched_from_ni', False):
                    # Recursively process children first (passing current item as parent)
                    self._recursive_recalculate_node(item['dettaglio'], item)
                    
                    # Calculate standard sum of children values
                    children_sum = sum(
                        child.get('valore', 0.0) 
                        for child in item['dettaglio'].values()
                    )
                    
                    # Apply special calculation rules if applicable
                    calculated_value = self._calculate_special_totals(item, canonical_name, children_sum)
                    
                    # Special case: A) Patrimonio netto needs to include "Patrimonio netto di terzi"
                    if canonical_name == 'A) Patrimonio netto' and parent_node and isinstance(parent_node, dict):
                        # Look for "Patrimonio netto di terzi" at the same level as "A) Patrimonio netto"
                        patrimonio_terzi = parent_node.get('Patrimonio netto di terzi', {}).get('valore', 0.0)
                        if patrimonio_terzi != 0.0:
                            calculated_value += patrimonio_terzi
                            logging.debug(f"Added 'Patrimonio netto di terzi' ({patrimonio_terzi}) to 'A) Patrimonio netto': {calculated_value}")
                    
                    # Update parent value with calculated total
                    item['valore'] = calculated_value

    def _calculate_special_totals(self, item: Dict[str, Any], canonical_name: str, children_sum: float) -> float:
        """
        Calculate totals for items with special calculation rules.
        
        This method handles financial statement items that require custom
        calculation logic instead of simple summation of children values.
        
        Special cases handled:
        1. C) Proventi e oneri finanziari: 15+16-17±17bis
        2. Imposte sul reddito: sum all except subtract "Proventi (oneri) consolidato"
        3. D) Rettifiche di valore: Rivalutazioni - Svalutazioni
        4. A) Patrimonio netto: include "Patrimonio netto di terzi"
        
        Args:
            item: Financial statement item dictionary
            canonical_name: Canonical name of the item
            children_sum: Standard sum of all children values
            
        Returns:
            Calculated total value according to special rules, or children_sum if no special rule applies
        """
        dettaglio = item.get('dettaglio', {})
        
        # CASO 1: C) Proventi e oneri finanziari
        # Formula: 15 + 16 - 17 ± 17bis
        if canonical_name == 'C) Proventi e oneri finanziari':
            total = 0.0
            
            # +15) Proventi da partecipazioni
            proventi_partecipazioni = dettaglio.get('15) Proventi da partecipazioni', {}).get('valore', 0.0)
            total += proventi_partecipazioni
            
            # +16) Altri proventi finanziari
            altri_proventi = dettaglio.get('16) Altri proventi finanziari', {}).get('valore', 0.0)
            total += altri_proventi
            
            # -17) Interessi e altri oneri finanziari
            interessi_oneri = dettaglio.get('17) Interessi e altri oneri finanziari', {}).get('valore', 0.0)
            total -= interessi_oneri
            
            # ±17-bis) Utile (perdita) su cambi (può essere positivo o negativo)
            utile_perdita_cambi = dettaglio.get('17-bis) Utile (perdita) su cambi', {}).get('valore', 0.0)
            total += utile_perdita_cambi
            
            logging.debug(f"Special calculation for '{canonical_name}': {proventi_partecipazioni} + {altri_proventi} - {interessi_oneri} + {utile_perdita_cambi} = {total}")
            return total
        
        # CASO 2: Imposte sul reddito dell'esercizio
        # Formula: sum all except "Proventi (oneri) consolidato"
        if canonical_name == "Imposte sul reddito dell'esercizio":
            total = 0.0
            
            for child_key, child_item in dettaglio.items():
                child_value = child_item.get('valore', 0.0)
                
                # Sottrarre invece di sommare per "Proventi (oneri) da adesione al regime di consolidato fiscale"
                if child_key == 'Proventi (oneri) da adesione al regime di consolidato fiscale':
                    total -= child_value
                    logging.debug(f"  Subtracting '{child_key}': -{child_value}")
                else:
                    total += child_value
                    logging.debug(f"  Adding '{child_key}': +{child_value}")
            
            logging.debug(f"Special calculation for '{canonical_name}': total = {total}")
            return total
        
        # CASO 3: D) Rettifiche di valore di attività finanziarie
        # Formula: Rivalutazioni - Svalutazioni
        if canonical_name == 'D) Rettifiche di valore di attività finanziarie':
            rivalutazioni = dettaglio.get('Rivalutazioni', {}).get('valore', 0.0)
            svalutazioni = dettaglio.get('Svalutazioni', {}).get('valore', 0.0)
            
            total = rivalutazioni - svalutazioni
            
            logging.debug(f"Special calculation for '{canonical_name}': {rivalutazioni} - {svalutazioni} = {total}")
            return total
        
        # CASO 4: A) Patrimonio netto
        # Formula: Sum also Patrimonio netto di terzi
        # Nota: "Patrimonio netto di terzi" is at the sime gearchiacal level but is to be considered as children
        if canonical_name == 'A) Patrimonio netto':
            logging.debug(f"Special calculation for '{canonical_name}': using children_sum = {children_sum} (will add 'Patrimonio netto di terzi' at parent level)")
            return children_sum
        return children_sum

    def _find_item_in_structure(self, node: Optional[Dict], canonical_name: str) -> Optional[Dict]:
        """
        Find specific item in hierarchical financial statement structure.
        
        Recursive search logic for locating specific financial statement items within the
        nested dictionary structure. It's used primarily for finding profit
        figures in both Income Statement and Balance Sheet for consistency validation.
        
        Args:
            node: Node to search within (can be None)
            canonical_name: Canonical name of item to find
            
        Returns:
            Dictionary containing item data or None if not found
        """
        if not isinstance(node, dict):
            return None
            
        # Direct match check
        for key, item in node.items():
            if key == canonical_name:
                return item
                
            # Recursive search in children
            if isinstance(item, dict):
                found = self._find_item_in_structure(
                    item.get('dettaglio', item), 
                    canonical_name
                )
                if found:
                    return found
                    
        return None

    def check_balance_sheet_equilibrium(self, attivo_total: float, passivo_total: float) -> ValidationResult:
        """
        Check balance sheet equilibrium with detailed result.
        
        Convenience method for external validation of balance sheet equilibrium
        that returns structured validation result instead of tuple.
        
        Args:
            attivo_total: Total assets value
            passivo_total: Total liabilities value
            
        Returns:
            Detailed validation result
        """
        status, diff = self._check_tolerance(attivo_total, passivo_total, attivo_total)
        tolerance = max(abs(attivo_total * self.tolerance_percentage), self.tolerance_minimum)
        
        return ValidationResult(
            status=status,
            reference_value=attivo_total,
            compared_value=passivo_total,
            difference=diff,
            tolerance_used=tolerance
        )

    def check_profit_consistency(self, ce_profit: float, sp_profit: float) -> ValidationResult:
        """
        Check profit consistency between statements with detailed result.
        
        Convenience method for external validation of profit consistency
        that returns structured validation result instead of tuple.
        
        Args:
            ce_profit: Profit from Income Statement
            sp_profit: Profit from Balance Sheet
            
        Returns:
            Detailed validation result
        """
        status, diff = self._check_tolerance(ce_profit, sp_profit, ce_profit)
        tolerance = max(abs(ce_profit * self.tolerance_percentage), self.tolerance_minimum)
        
        return ValidationResult(
            status=status,
            reference_value=ce_profit,
            compared_value=sp_profit,
            difference=diff,
            tolerance_used=tolerance
        )