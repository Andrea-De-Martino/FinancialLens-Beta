# data_validator.py

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
        
        # Calculate total attivo and passivo exactly as original
        tot_attivo = sum(item.get('valore', 0.0) for item in sp.get('attivo', {}).values())
        tot_passivo = sum(item.get('valore', 0.0) for item in sp.get('passivo', {}).values())
        
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
            # Find profit items in both statements exactly as original
            utile_ce_node = self._find_item_in_structure(
                data.get('conto_economico', {}), 
                "Utile (perdita) dell'esercizio"
            ) or {}
            utile_sp_node = self._find_item_in_structure(
                sp, 
                "IX - Utile (perdita) dell'esercizio"
            ) or {}
            
            val_ce = utile_ce_node.get('valore')
            val_sp = utile_sp_node.get('valore')

            if val_ce is not None and val_sp is not None:
                status, diff = self._check_tolerance(val_ce, val_sp, val_ce)
                validations['coerenza_utile_esercizio'] = {
                    "status": status, 
                    "utile_conto_economico": round(val_ce, 2), 
                    "utile_stato_patrimoniale": round(val_sp, 2), 
                    "discrepanza": round(diff, 2)
                }
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
        - 'success': Values are effectively identical (within 2 euro difference)
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

    def _recursive_recalculate_totals(self, data: Dict[str, Any]) -> None:
        """
        Recursively recalculate parent totals from children values.
        
        This method preserves the exact recursive calculation logic from the
        original parser, including the critical rule that nodes enriched from
        Nota Integrativa should not have their totals recalculated since they
        contain authoritative values from supplementary documentation.
        
        The recalculation ensures that parent node values accurately reflect
        the sum of their children, which is essential for proper validation
        of hierarchical financial statement structures.
        
        Args:
            data: Financial statement data structure to process
        """
        # Process Balance Sheet sections exactly as original
        sp = data.get('stato_patrimoniale', {})
        if sp:
            if 'attivo' in sp:
                self._recursive_recalculate_node(sp['attivo'])
            if 'passivo' in sp:
                self._recursive_recalculate_node(sp['passivo'])

        # Process Income Statement exactly as original
        self._recursive_recalculate_node(data.get('conto_economico', {}))

    def _recursive_recalculate_node(self, node: Any) -> None:
        """
        Recursively recalculate totals for a single node and its children.
        
        This helper method implements the core recursive calculation logic,
        preserving the exact behavior including the enriched_from_ni flag
        handling that prevents overwriting authoritative Nota Integrativa data.
        
        Args:
            node: Node to process (can be dict or other type)
        """
        if not isinstance(node, dict):
            return
            
        for item in node.values():
            if isinstance(item, dict) and 'dettaglio' in item and item.get('dettaglio'):
                # Skip recalculation if enriched from Nota Integrativa
                if not item.get('enriched_from_ni', False):
                    # Recursively process children first
                    self._recursive_recalculate_node(item['dettaglio'])
                    
                    # Calculate sum of children values
                    children_sum = sum(
                        child.get('valore', 0.0) 
                        for child in item['dettaglio'].values()
                    )
                    
                    # Update parent value with children sum
                    item['valore'] = children_sum

    def _find_item_in_structure(self, node: Optional[Dict], canonical_name: str) -> Optional[Dict]:
        """
        Find specific item in hierarchical financial statement structure.
        
        This method preserves the exact recursive search logic from the original
        parser for locating specific financial statement items within the
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