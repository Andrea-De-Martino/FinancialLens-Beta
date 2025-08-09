# configuration_manager.py

import yaml
import re
from pathlib import Path
from typing import Dict, Any, Tuple, List
import logging


class ConfigurationManager:
    """
    Manages loading and distribution of configuration across all parser modules.
    
    This class centralizes configuration management for the enhanced financial statement
    parser system with integrated reclassification capabilities. It handles loading
    configuration from multiple YAML files, merging them into a unified structure,
    and providing specialized configuration subsets to individual modules based on
    their specific needs.
    
    The manager maintains backward compatibility with the original monolithic
    configuration structure while enabling the modular architecture. It preserves
    all existing configuration processing logic, including the complex contextual
    and parent mapping generation that is critical for the hierarchical financial
    statement processing.
    
    Enhanced capabilities include:
    - Financial reclassification configuration management
    - Mapping template path resolution and validation
    - Integrated validation for all parser modules including reclassifier
    - Comprehensive configuration statistics and monitoring
    
    During the transition phase, it can load from either the original single
    config.yaml file or from the new modular configuration structure, ensuring
    seamless migration without breaking existing functionality.
    """

    def __init__(self, config_path: Path):
        """
        Initialize configuration manager and load all configuration data.
        
        Args:
            config_path: Path to configuration file or directory
        """
        self.config_path = config_path
        self.config = self._load_configuration()
        
        # Generate derived configuration objects exactly as original parser
        self.inverted_configs, self.parent_map = self._create_contextual_and_parent_configs()
        
        # Process ignore patterns exactly as original
        self.processed_ignore_patterns = self._process_ignore_patterns()
        
        # Initialize reclassification paths and validate availability
        self._initialize_reclassification_config()

    def _load_configuration(self) -> Dict[str, Any]:
        """
        Load configuration from file(s).
        
        This method maintains backward compatibility by detecting whether
        we're loading from the original monolithic config.yaml or from
        the new modular structure. It ensures identical configuration
        content regardless of the file organization.
        
        Returns:
            Unified configuration dictionary with same structure as original
        """
        if self.config_path.is_file():
            # Load from single configuration file (backward compatibility)
            return self._load_single_config_file(self.config_path)
        elif self.config_path.is_dir():
            # Load from modular configuration directory (enhanced structure)
            return self._load_modular_configs(self.config_path)
        else:
            raise FileNotFoundError(f"Configuration path not found: {self.config_path}")

    def _load_single_config_file(self, config_file: Path) -> Dict[str, Any]:
        """
        Load configuration from single YAML file (original structure).
        
        Preserves exact same loading behavior as original parser to ensure
        complete compatibility during transition phase.
        
        Args:
            config_file: Path to single configuration file
            
        Returns:
            Complete configuration dictionary
        """
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Remove rendiconto_finanziario section as per requirements
            if 'rendiconto_finanziario' in config:
                del config['rendiconto_finanziario']
                logging.info("Removed rendiconto_finanziario section from configuration")
            
            return config
        except Exception as e:
            logging.error(f"Failed to load configuration from {config_file}: {e}")
            raise

    def _load_modular_configs(self, config_dir: Path) -> Dict[str, Any]:
        """
        Load and merge configuration from multiple YAML files.
        
        This method handles the modular configuration structure with enhanced
        capabilities for reclassification and advanced features. It merges all
        configuration files into a unified structure that maintains compatibility
        with existing code while enabling new functionality.
        
        Args:
            config_dir: Directory containing configuration files
            
        Returns:
            Merged configuration dictionary with enhanced capabilities
        """
        config = {}
        
        # Define expected configuration files and their merge strategy
        config_files = {
            'config_main.yaml': 'merge_root',
            'config_balance_sheet.yaml': 'merge_as_stato_patrimoniale',
            'config_income_statement.yaml': 'merge_as_conto_economico', 
            'config_enrichment.yaml': 'merge_root',
            'config_constants.yaml': 'merge_root'
        }
        
        for filename, merge_strategy in config_files.items():
            file_path = config_dir / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_config = yaml.safe_load(f) or {}
                    
                    if merge_strategy == 'merge_root':
                        config.update(file_config)
                    elif merge_strategy == 'merge_as_stato_patrimoniale':
                        config['stato_patrimoniale'] = file_config
                    elif merge_strategy == 'merge_as_conto_economico':
                        config['conto_economico'] = file_config
                        
                    logging.info(f"Loaded configuration from {filename}")
                except Exception as e:
                    logging.warning(f"Failed to load {filename}: {e}")
        
        return config

    def _initialize_reclassification_config(self) -> None:
        """
        Initialize reclassification configuration paths and validate availability.
        
        Sets up the file paths and validates the availability of the mapping
        template required for financial reclassification functionality.
        """
        # Determine base configuration directory
        if self.config_path.is_file():
            # Single file config - look in same directory
            base_dir = self.config_path.parent
        else:
            # Modular config - use the config directory
            base_dir = self.config_path
        
        # Set mapping template path
        self.mapping_template_path = base_dir / 'mapping_template.xlsx'
        
        # Validate availability and log status
        if self.mapping_template_path.exists():
            logging.info(f"Reclassification mapping template found: {self.mapping_template_path}")
            self.reclassification_available = True
        else:
            logging.warning(f"Reclassification mapping template not found: {self.mapping_template_path}")
            logging.warning("Financial reclassification features will be limited")
            self.reclassification_available = False

    def _create_contextual_and_parent_configs(self) -> Tuple[Dict[str, Dict[str, List[str]]], Dict[str, str]]:
        """
        Create contextual and parent mapping configurations.
        
        This method preserves the exact _create_contextual_and_parent_configs
        logic from the original parser. It generates the complex inverted
        configuration mappings and parent relationships that are critical
        for the hierarchical financial statement processing.
        
        The generated structures are used by the text processing and hierarchy
        management modules for synonym matching and parent-child relationship
        management.
        
        Returns:
            Tuple of (contextual configs, parent map)
        """
        contextual_configs: Dict[str, Dict[str, List[str]]] = {}
        parent_map: Dict[str, str] = {}
        self.branch_map: Dict[str, str] = {}

        def recurse_node(node: Dict, current_map: Dict[str, List[str]], branch_key: str, parent_key: str = None):
            for key, config_item in node.items():
                if not isinstance(config_item, dict):
                    continue
                
                parent_map[key] = parent_key if parent_key else branch_key
                self.branch_map[key] = branch_key

                synonyms = config_item.get('sinonimi', []) + [key]
                for synonym in synonyms:
                    normalized_synonym = self._normalize_text_for_matching(synonym)
                    if normalized_synonym not in current_map:
                        current_map[normalized_synonym] = []
                    if key not in current_map[normalized_synonym]:
                        current_map[normalized_synonym].append(key)
                
                if 'dettaglio' in config_item:
                    recurse_node(config_item['dettaglio'], current_map, branch_key, key)

        # Process financial statement sections exactly as original
        for section in ['stato_patrimoniale', 'conto_economico']:
            if section in self.config:
                section_map: Dict[str, List[str]] = {}
                if section == 'stato_patrimoniale':
                    if 'attivo' in self.config[section]:
                        recurse_node(self.config[section]['attivo'], section_map, 'attivo')
                    if 'passivo' in self.config[section]:
                        recurse_node(self.config[section]['passivo'], section_map, 'passivo')
                else:
                    for branch_key, branch_node in self.config[section].items():
                        self.branch_map[branch_key] = branch_key
                        recurse_node({branch_key: branch_node}, section_map, branch_key)
                
                contextual_configs[section] = section_map
                
        return contextual_configs, parent_map

    def _normalize_text_for_matching(self, text: str) -> str:
        """
        Normalize text for matching exactly as original parser.
        
        Preserves the exact _normalize_text logic from original parser
        when used with for_matching=True parameter.
        
        Args:
            text: Text to normalize
            
        Returns:
            Normalized text for matching
        """
        if not text:
            return ""
        text_str = str(text).strip().lower()
        text_str = re.sub(r'[\t\r]', ' ', text_str)
        text_str = text_str.replace('\n', ' ')
        text_str = re.sub(r'[^a-z0-9\s]', '', text_str)
        return re.sub(r'\s+', ' ', text_str.strip())

    def _process_ignore_patterns(self) -> List[str]:
        """
        Process ignore patterns exactly as original parser.
        
        Applies text normalization to ignore patterns in the same way
        as the original parser initialization.
        
        Returns:
            List of normalized ignore patterns
        """
        ignore_patterns = self.config.get('ignore_patterns', [])
        return [self._normalize_text_for_matching(p) for p in ignore_patterns]

    def get_pdf_extractor_config(self) -> Dict[str, Any]:
        """
        Get configuration subset for PDF extraction.
        
        Returns:
            Configuration dict containing PDF extraction settings
        """
        pdf_config = self.config.get('pdf_extraction', {})
        
        return {
            'raw_text_sections': self.config.get('raw_text_sections', []),
            'table_settings': pdf_config.get('table_settings', {}),
            'section_patterns': pdf_config.get('section_patterns', {}),
            'abbreviated_format_indicators': pdf_config.get('abbreviated_format_indicators', [])
        }

    def get_text_processor_config(self) -> Dict[str, Any]:
        """
        Get configuration subset for text processing.
        
        Returns:
            Configuration dict containing text processing settings and mappings
        """
        settings = self.config.get('parser_settings', {})
        
        return {
            'fuzzy_score_threshold': settings.get('fuzzy_score_threshold', 90),
            'ignore_fuzzy_score_threshold': settings.get('ignore_fuzzy_score_threshold', 90),
            'inverted_configs': self.inverted_configs,
            'parent_map': self.parent_map,
            'branch_map': self.branch_map,
            'ignore_patterns': self.processed_ignore_patterns
        }

    def get_hierarchy_config(self) -> Dict[str, Any]:
        """
        Get configuration subset for hierarchy management.
        
        Returns:
            Configuration dict containing hierarchy building settings
        """
        return {
            'parent_map': self.parent_map,
            'branch_map': self.branch_map,
            'stato_patrimoniale': self.config.get('stato_patrimoniale', {}),
            'conto_economico': self.config.get('conto_economico', {})
        }

    def get_enrichment_config(self) -> Dict[str, Any]:
        """
        Get configuration subset for enrichment processing.
        
        Returns:
            Configuration dict containing enrichment settings and rules
        """
        settings = self.config.get('parser_settings', {})
        
        return {
            'enrichment_rules': self.config.get('enrichment_rules', {}),
            'enrichment_column_keywords': self.config.get('enrichment_column_keywords', {}),
            'enrichment_score_threshold': settings.get('enrichment_score_threshold'),
            'enrichment_high_confidence_threshold': settings.get('enrichment_high_confidence_threshold'),
            'nota_integrativa_columns': self.config.get('nota_integrativa_columns', {}),
            'processing_settings': self.config.get('processing_settings', {})
        }

    def get_validation_config(self) -> Dict[str, Any]:
        """
        Get configuration subset for data validation.
        
        Returns:
            Configuration dict containing validation tolerance settings
        """
        return {
            'validation_settings': {
                'tolerance_percentage': 0.01,
                'tolerance_minimum': 2.0,
                'immediate_success_threshold': 2.0
            }
        }

    def get_reclassifier_config(self) -> Path:
        """
        Get configuration for financial reclassifier.
        
        Provides the path to the configuration directory containing the
        mapping template required for financial reclassification operations.
        This enables the FinancialReclassifier to locate and load its
        mapping rules for transforming Italian financial statements into
        international format.
        
        Returns:
            Path to configuration directory containing mapping template
            
        Raises:
            FileNotFoundError: If configuration directory is not accessible
        """
        # Determine base configuration directory
        if self.config_path.is_file():
            # Single file config - return parent directory
            config_dir = self.config_path.parent
        else:
            # Modular config - return the config directory
            config_dir = self.config_path
        
        # Validate directory accessibility
        if not config_dir.exists():
            raise FileNotFoundError(f"Configuration directory not found: {config_dir}")
        
        # Log reclassification configuration status
        if self.reclassification_available:
            logging.debug(f"Reclassifier configuration directory: {config_dir}")
        else:
            logging.warning(f"Reclassifier configuration directory available but mapping template missing: {config_dir}")
        
        return config_dir

    def get_full_config(self) -> Dict[str, Any]:
        """
        Get complete configuration for backward compatibility.
        
        Returns complete configuration dictionary that matches the structure
        expected by the original parser implementation.
        
        Returns:
            Complete configuration dictionary
        """
        return self.config.copy()

    def get_financial_schema_config(self, section: str) -> Dict[str, Any]:
        """
        Get specific financial statement schema configuration.
        
        Args:
            section: Section name ('stato_patrimoniale' or 'conto_economico')
            
        Returns:
            Schema configuration for the specified section
        """
        return self.config.get(section, {})

    def get_parser_settings(self) -> Dict[str, Any]:
        """
        Get parser processing settings.
        
        Returns:
            Dictionary containing all parser processing parameters
        """
        return self.config.get('parser_settings', {})

    def get_output_settings(self) -> Dict[str, Any]:
        """
        Get output formatting and file naming settings.
        
        Returns:
            Configuration for output file generation
        """
        output_config = self.config.get('output_settings', {})
        processing_config = self.config.get('processing_thresholds', {})
        
        return {
            'output_prefixes': output_config.get('prefixes', {}),
            'retry_settings': {
                'max_attempts': processing_config.get('max_retry_attempts'),
                'ni_search_page_limit': processing_config.get('ni_search_page_limit')
            }
        }

    def is_reclassification_available(self) -> bool:
        """
        Check if financial reclassification capabilities are available.
        
        Determines whether the system has all required components for
        financial reclassification operations, including the mapping
        template and configuration files.
        
        Returns:
            True if reclassification is fully available, False otherwise
        """
        return self.reclassification_available

    def get_reclassification_status(self) -> Dict[str, Any]:
        """
        Get detailed status of reclassification configuration.
        
        Provides comprehensive information about the availability and
        configuration status of financial reclassification capabilities.
        
        Returns:
            Dictionary containing reclassification status details
        """
        return {
            'available': self.reclassification_available,
            'mapping_template_path': str(self.mapping_template_path),
            'mapping_template_exists': self.mapping_template_path.exists(),
            'config_directory': str(self.config_path if self.config_path.is_dir() else self.config_path.parent),
            'features_enabled': [
                'Italian to International Format Conversion',
                'P&L, Assets, Liabilities Transformation',
                'Cascading Financial Calculations',
                'Balance Sheet Equilibrium Validation'
            ] if self.reclassification_available else []
        }

    def validate_configuration(self) -> bool:
        """
        Validate that all required configuration sections are present.
        
        Ensures that the configuration contains all necessary sections
        for proper parser operation, including enhanced validation for
        reclassification capabilities.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        required_sections = [
            'parser_settings',
            'stato_patrimoniale', 
            'conto_economico',
            'enrichment_rules',
            'raw_text_sections',
            'ignore_patterns'
        ]
        
        missing_sections = []
        for section in required_sections:
            if section not in self.config:
                missing_sections.append(section)
        
        if missing_sections:
            logging.error(f"Missing required configuration sections: {missing_sections}")
            return False
        
        # Enhanced validation for reclassification configuration
        if not self.reclassification_available:
            logging.info("Reclassification configuration not fully available - limited functionality")
            # Note: This is not a failure condition as reclassification is an enhancement
        
        return True

    def get_comprehensive_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about all configuration aspects.
        
        Provides detailed analytics about the configuration setup including
        parser capabilities, reclassification status, and module readiness.
        
        Returns:
            Dictionary containing comprehensive configuration statistics
        """
        stats = {
            'configuration_type': 'modular' if self.config_path.is_dir() else 'single_file',
            'configuration_path': str(self.config_path),
            'total_sections': len(self.config),
            'contextual_configs': len(self.inverted_configs),
            'parent_mappings': len(self.parent_map),
            'branch_mappings': len(self.branch_map),
            'ignore_patterns': len(self.processed_ignore_patterns),
            
            # Financial statement schema statistics
            'balance_sheet_items': len(self._count_schema_items('stato_patrimoniale')),
            'income_statement_items': len(self._count_schema_items('conto_economico')),
            
            # Enhancement capabilities
            'enrichment_rules': len(self.config.get('enrichment_rules', {})),
            'reclassification_available': self.reclassification_available,
            'mapping_template_path': str(self.mapping_template_path),
            
            # Module readiness
            'modules_supported': [
                'PDFExtractor',
                'TextProcessor', 
                'HierarchyManager',
                'EnrichmentEngine',
                'DataValidator',
                'FinancialReclassifier' if self.reclassification_available else 'FinancialReclassifier (Limited)'
            ]
        }
        
        return stats

    def _count_schema_items(self, section: str) -> List[str]:
        """
        Count items in a financial statement schema section.
        
        Args:
            section: Schema section to count
            
        Returns:
            List of item names in the schema section
        """
        def collect_items(node: Any, items: List[str] = None) -> List[str]:
            if items is None:
                items = []
            
            if isinstance(node, dict):
                for key, value in node.items():
                    items.append(key)
                    if isinstance(value, dict) and 'dettaglio' in value:
                        collect_items(value['dettaglio'], items)
            
            return items
        
        schema_section = self.config.get(section, {})
        return collect_items(schema_section)

    def get_module_config_summary(self) -> Dict[str, Dict[str, Any]]:
        """
        Get summary of configuration provided to each module.
        
        Provides an overview of what configuration each parser module
        receives, useful for debugging and system analysis.
        
        Returns:
            Dictionary mapping module names to their configuration summaries
        """
        return {
            'PDFExtractor': {
                'raw_text_sections': len(self.config.get('raw_text_sections', [])),
                'table_settings_configured': True,
                'section_patterns_configured': True
            },
            'TextProcessor': {
                'contextual_configs': len(self.inverted_configs),
                'fuzzy_threshold': self.config.get('parser_settings', {}).get('fuzzy_score_threshold', 90),
                'ignore_patterns': len(self.processed_ignore_patterns)
            },
            'HierarchyManager': {
                'parent_mappings': len(self.parent_map),
                'branch_mappings': len(self.branch_map),
                'schema_sections': len([s for s in ['stato_patrimoniale', 'conto_economico'] if s in self.config])
            },
            'EnrichmentEngine': {
                'enrichment_rules': len(self.config.get('enrichment_rules', {})),
                'column_keywords_configured': 'enrichment_column_keywords' in self.config,
                'nota_integrativa_columns_configured': True
            },
            'DataValidator': {
                'validation_settings_configured': True,
                'tolerance_settings_available': True
            },
            'FinancialReclassifier': {
                'configuration_available': self.reclassification_available,
                'mapping_template_path': str(self.mapping_template_path),
                'config_directory_accessible': self.config_path.exists()
            }
        }