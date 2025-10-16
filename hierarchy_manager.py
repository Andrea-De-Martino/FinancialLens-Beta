import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class HierarchyContext:
    """Context for hierarchy building during financial statement processing."""
    current_context: Optional[str]
    parent_stack: List[Dict[str, Any]]
    is_abbreviated_format: bool


class HierarchyManager:
    """
    Manages hierarchical data construction and parent stack logic for financial statements.
    
    This module represents the most critical component of the financial
    statement parsing system. It handles the parent-child relationship
    management that enables the parser to understand the hierarchical structure of
    financial statements while processing them in linear fashion from PDF documents.
    
    The core challenge addressed by this module is maintaining hierarchical context
    during sequential processing. As the parser encounters financial items line by
    line, it must:
    
    1. Determine each item's position in the financial statement hierarchy
    2. Manage parent-child relationships dynamically using a stack-based approach
    3. Aggregate child values to parent totals when hierarchical sections complete
    4. Handle special cases like abbreviated format temporal classifications
    5. Build the final nested dictionary structure that represents the financial statement
    
    The parent stack mechanism is a crucial point of this system. It tracks the current
    hierarchical context as parsing progresses, automatically pushing new parents
    when encountered and popping completed parents when their sections end. This
    approach allows linear PDF processing to produce correctly structured hierarchical
    financial data.
    
    The module also handles the complex value aggregation logic that determines when
    parent nodes should sum their children versus preserving their original values,
    which is crucial for maintaining the mathematical integrity of financial statements.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize hierarchy manager with financial statement schema configuration.
        
        Args:
            config: Configuration containing parent mappings, branch mappings, and schemas
        """
        self.parent_map = config.get('parent_map', {})
        self.branch_map = config.get('branch_map', {})
        self.stato_patrimoniale_config = config.get('stato_patrimoniale', {})
        self.conto_economico_config = config.get('conto_economico', {})

    def process_financial_item(self, financial_item: Dict[str, Any], 
                              context: HierarchyContext) -> HierarchyContext:
        """
        Process a single financial item and update hierarchy context.
        
        The method handles the decision-making process for each financial
        item: determining its hierarchical position, managing parent stack state,
        processing completed parents, and preparing for potential children. The
        logic carefully maintains the stack invariant that represents the current
        hierarchical path through the financial statement structure.
        
        Special handling is included for abbreviated format documents where
        temporal classifications (entro/oltre esercizio) are embedded within
        parent items rather than appearing as separate line items.
        
        Args:
            financial_item: Raw financial item data from text processing. This is a
                           direct reference to the dictionary object to allow for
                           in-place modifications (e.g., adding maturity details).
            context: Current hierarchy building context including parent stack.
            
        Returns:
            Updated hierarchy context after processing the item.
        """
        # This method now works directly with the 'financial_item' dictionary
        # object passed from the main parser. This ensures that any modifications made
        # here (like adding maturity details via the parent stack) are reflected
        # in the object that gets stored in the final flat data list.
               
        # Determine parent relationship for this item
        item_parent_name = self.parent_map.get(financial_item['voce_canonica'])
        current_parent_name = (
            context.parent_stack[-1]['voce_canonica'] 
            if context.parent_stack else None
        )
        
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            stack_str = ' -> '.join([p['voce_canonica'] for p in context.parent_stack])
            logging.debug(
                f"Processing: '{financial_item['voce_originale']}' -> '{financial_item['voce_canonica']}' "
                f"(Expected parent: '{item_parent_name}')"
            )
            logging.debug(f"  Current stack: [{stack_str}]")

        # Manage parent stack - pop parents until we find the correct parent
        while (context.parent_stack and 
               item_parent_name != context.parent_stack[-1]['voce_canonica']):
            closed_parent = context.parent_stack.pop()
            self._process_completed_parent(closed_parent)
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f"    -> Popped: '{closed_parent['voce_canonica']}' (completed)")
        
        # Add item to current parent's children buffer if parent exists
        if context.parent_stack:
            if '_children_buffer' not in context.parent_stack[-1]:
                context.parent_stack[-1]['_children_buffer'] = []
            context.parent_stack[-1]['_children_buffer'].append(financial_item)
        
        # Check if this item is a potential parent (has children in schema)
        config_node = self._get_config_node(financial_item['voce_canonica'])
        is_potential_parent = config_node and 'dettaglio' in config_node
        
        # This logic ensures that a potential parent with a zero value from the PDF is marked to be
        # calculated from its children later.
        if is_potential_parent and financial_item['valore'] == 0.0:
            financial_item['valore'] = 0.0
        
        # Push item onto parent stack if it's a potential parent
        if is_potential_parent:
            context.parent_stack.append(financial_item)
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(f"    -> Pushed: '{financial_item['voce_canonica']}' (new parent)")

        return context

    def handle_abbreviated_scadenze(self, item_data: Dict[str, Any], 
                                   parent_stack: List[Dict[str, Any]]) -> bool:
        """
        Handle special temporal classification processing for abbreviated format.
        
        This method preserves the exact logic for handling "esigibili entro/oltre"
        classifications in abbreviated format documents. These appear as sub-lines
        within parent items rather than as separate financial items, requiring
        special processing to associate them with their parent nodes.
        
        Args:
            item_data: Raw item data that might contain temporal classification
            parent_stack: Current parent stack for association
            
        Returns:
            True if item was processed as temporal classification, False otherwise
        """
        if not parent_stack:
            return False
        
        line_desc = item_data.get('voce_originale', '')
        norm_line_desc = line_desc.lower().replace('\n', ' ')
        line_value = item_data.get('valore', 0.0)
        
        maturity_key = None
        if "esigibili" in norm_line_desc and "entro" in norm_line_desc:
            maturity_key = "entro"
        elif "esigibili" in norm_line_desc and "oltre" in norm_line_desc:
            maturity_key = "oltre"
        
        if maturity_key and line_value != 0.0:
            parent_item = parent_stack[-1]
            if '_dettaglio_scadenza' not in parent_item:
                parent_item['_dettaglio_scadenza'] = {}
            parent_item['_dettaglio_scadenza'][maturity_key] = line_value
            
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(
                    f"    -> Short Format: Associated '{maturity_key}' with parent "
                    f"'{parent_item['voce_canonica']}' (value: {line_value})"
                )
            return True
        
        return False

    def _process_completed_parent(self, parent_item: Dict[str, Any]) -> None:
        """
        Process a parent when it's complete (no more children expected).
        
        This method preserves the exact logic from the original parser for
        handling completed parent nodes. It performs the critical value
        aggregation that ensures parent totals correctly reflect the sum
        of their children when the parent has no explicit value.
        
        The method also handles cleanup of temporary data structures used
        during the hierarchy building process.
        
        Args:
            parent_item: Parent item that has been completed
        """
        children_buffer = parent_item.get('_children_buffer', [])
        
        # Aggregate children values to parent if parent has zero value
        if children_buffer and parent_item.get('valore', 0.0) == 0.0:
            parent_item['valore'] = sum(child['valore'] for child in children_buffer)
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                logging.debug(
                    f"    -> Aggregated: '{parent_item['voce_canonica']}' "
                    f"value = {parent_item['valore']} (sum of {len(children_buffer)} children)"
                )
        
        # Clean up temporary children buffer
        if '_children_buffer' in parent_item:
            del parent_item['_children_buffer']

    def build_hierarchical_structure(self, config_node: Dict[str, Any], 
                                   data_map: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Build final hierarchical structure from flat data map.
        
        It transforms the flat data map produced by the parsing process 
        into the final nested dictionary structure that represents the 
        complete financial statement hierarchy.
        
        The method handles several critical aspects:
        1. Recursive traversal of the configuration schema
        2. Lookup of actual data items in the flat data map
        3. Special handling of temporal classification data
        4. Recursive construction of child hierarchies
        5. Assignment of child structures to parent nodes
        
        Special attention is paid to temporal classification data that may
        have been collected during abbreviated format processing.
        
        Args:
            config_node: Configuration schema for this hierarchy level
            data_map: Flat mapping of canonical names to item data
            
        Returns:
            Hierarchical nested dictionary structure
        """
        built_node: Dict[str, Any] = {}
        
        for canonical_name, value in config_node.items():
            item_data = data_map.get(canonical_name)
            current_node = item_data.copy() if item_data else {}
            
            # Handle temporal classification data from abbreviated format
            if current_node and '_dettaglio_scadenza' in current_node:
                current_node.setdefault('dettaglio', {})
                scadenze = current_node['_dettaglio_scadenza']
                branch = self.branch_map.get(canonical_name)
                
                # Create temporal breakdown entries
                if scadenze.get('entro'):
                    voce_canonica_entro = (
                        "Crediti (importo esigibile entro l'esercizio successivo)" 
                        if branch == 'attivo' else 
                        "Debiti (importo esigibile entro l'esercizio successivo)"
                    )
                    current_node['dettaglio'][voce_canonica_entro] = {
                        'voce_canonica': voce_canonica_entro,
                        'valore': scadenze['entro'],
                        'voce_originale': "esigibili entro l'esercizio successivo",
                        'score': 100
                    }
                
                if scadenze.get('oltre'):
                    voce_canonica_oltre = (
                        "Crediti (importo esigibile oltre l'esercizio successivo)" 
                        if branch == 'attivo' else 
                        "Debiti (importo esigibile oltre l'esercizio successivo)"
                    )
                    current_node['dettaglio'][voce_canonica_oltre] = {
                        'voce_canonica': voce_canonica_oltre,
                        'valore': scadenze['oltre'],
                        'voce_originale': "esigibili oltre l'esercizio successivo",
                        'score': 100
                    }
                
                # Clean up temporary data
                del current_node['_dettaglio_scadenza']

            # Build children hierarchy if not already present and config exists
            if 'dettaglio' not in current_node:
                children_config = value.get('dettaglio') if isinstance(value, dict) else None
                if children_config:
                    children_structure = self.build_hierarchical_structure(
                        children_config, data_map
                    )
                    if children_structure:
                        if not current_node:
                            current_node = {'voce_canonica': canonical_name}
                        current_node['dettaglio'] = children_structure
            
            # Add node to built structure if it has content
            if current_node:
                built_node[canonical_name] = current_node
        
        return built_node

    def finalize_hierarchy_context(self, context: HierarchyContext) -> None:
        """
        Finalize hierarchy context by processing all remaining parents in stack.
        
        This method ensures that all parent items remaining in the stack
        are properly processed when parsing completes. This is essential
        for ensuring all value aggregations are completed correctly.
        
        Args:
            context: Hierarchy context to finalize
        """
        while context.parent_stack:
            completed_parent = context.parent_stack.pop()
            self._process_completed_parent(completed_parent)

    def _get_config_node(self, canonical_name: str) -> Optional[Dict]:
        """
        Get configuration node for a canonical name.
        
        This method searches through the financial statement schema configuration
        to find the configuration node corresponding to a canonical name. It's
        used to determine if an item is a potential parent (has children) and
        to access other configuration metadata.
        
        Args:
            canonical_name: Canonical name to look up
            
        Returns:
            Configuration node dictionary or None if not found
        """
        def find_in_dict(node: Dict, name: str) -> Optional[Dict]:
            if name in node:
                return node[name]
            for key, value in node.items():
                if isinstance(value, dict):
                    found = find_in_dict(value, name)
                    if found is not None:
                        return found
            return None
        
        # Search in balance sheet configuration
        if self.stato_patrimoniale_config:
            found = find_in_dict(self.stato_patrimoniale_config, canonical_name)
            if found is not None:
                return found
        
        # Search in income statement configuration
        if self.conto_economico_config:
            found = find_in_dict(self.conto_economico_config, canonical_name)
            if found is not None:
                return found
        
        return None

    def create_hierarchy_context(self, current_context: Optional[str] = None, 
                               is_abbreviated_format: bool = False) -> HierarchyContext:
        """
        Create initial hierarchy context for processing.
        
        Factory method to create a properly initialized hierarchy context
        for beginning financial statement processing.
        
        Args:
            current_context: Initial financial statement context
            is_abbreviated_format: Whether document is in abbreviated format
            
        Returns:
            Initialized hierarchy context
        """
        return HierarchyContext(
            current_context=current_context,
            parent_stack=[],
            is_abbreviated_format=is_abbreviated_format
        )

    def get_hierarchy_statistics(self, data_map: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Get statistics about the hierarchical structure.
        
        Provides analytical information about the parsed financial statement
        structure, useful for debugging and validation purposes.
        
        Args:
            data_map: Flat data map to analyze
            
        Returns:
            Dictionary containing hierarchy statistics
        """
        stats = {
            'total_items': len(data_map),
            'items_with_children': 0,
            'items_with_values': 0,
            'items_from_ni': 0,
            'avg_score': 0.0
        }
        
        total_score = 0
        for item in data_map.values():
            if isinstance(item, dict):
                if 'dettaglio' in item:
                    stats['items_with_children'] += 1
                if item.get('valore', 0.0) != 0.0:
                    stats['items_with_values'] += 1
                if item.get('from_ni', False):
                    stats['items_from_ni'] += 1
                if 'score' in item:
                    total_score += item['score']
        
        if stats['total_items'] > 0:
            stats['avg_score'] = total_score / stats['total_items']
        
        return stats

    def validate_hierarchy_integrity(self, hierarchical_data: Dict[str, Any]) -> bool:
        """
        Validate the integrity of the hierarchical structure.
        
        Performs consistency checks on the built hierarchical structure
        to ensure mathematical and structural integrity.
        
        Args:
            hierarchical_data: Complete hierarchical financial statement data
            
        Returns:
            True if hierarchy integrity is valid, False otherwise
        """
        def validate_node(node: Dict[str, Any], path: str = "") -> bool:
            if not isinstance(node, dict):
                return True
            
            for key, item in node.items():
                current_path = f"{path}.{key}" if path else key
                
                if isinstance(item, dict):
                    # Check if item has both value and children
                    has_value = 'valore' in item and item['valore'] != 0.0
                    has_children = 'dettaglio' in item and item['dettaglio']
                    
                    if has_children:
                        # Validate children recursively
                        if not validate_node(item['dettaglio'], current_path):
                            return False
                        
                        # Skip value validation for enriched items
                        if not item.get('enriched_from_ni', False) and has_value:
                            # Calculate children sum
                            children_sum = sum(
                                child.get('valore', 0.0) 
                                for child in item['dettaglio'].values() 
                                if isinstance(child, dict)
                            )
                            
                            # Allow small tolerance for rounding
                            tolerance = max(abs(item['valore'] * 0.001), 0.01)
                            if abs(item['valore'] - children_sum) > tolerance:
                                logging.warning(
                                    f"Hierarchy integrity warning at {current_path}: "
                                    f"parent value {item['valore']} != children sum {children_sum}"
                                )
            
            return True
        
        try:
            return validate_node(hierarchical_data)
        except Exception as e:
            logging.error(f"Hierarchy validation failed: {e}")
            return False