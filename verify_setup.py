#!/usr/bin/env python3
"""
Setup Verification Script
Checks that all components are properly configured
"""

import sys
import os
from pathlib import Path

def check_imports():
    """Check that all modules can be imported"""
    print("Checking imports...")
    errors = []
    
    try:
        from data.fetch_data import MemecoinDataFetcher
        print("  ✓ data.fetch_data")
    except Exception as e:
        errors.append(f"data.fetch_data: {e}")
        print(f"  ✗ data.fetch_data: {e}")
    
    try:
        from analysis.volatility_regimes import VolatilityRegimeAnalyzer
        print("  ✓ analysis.volatility_regimes")
    except Exception as e:
        errors.append(f"analysis.volatility_regimes: {e}")
        print(f"  ✗ analysis.volatility_regimes: {e}")
    
    try:
        from strategies.base_strategy import MeanReversionStrategy, MomentumStrategy
        print("  ✓ strategies.base_strategy")
    except Exception as e:
        errors.append(f"strategies.base_strategy: {e}")
        print(f"  ✗ strategies.base_strategy: {e}")
    
    try:
        from backtesting.engine import BacktestEngine, BacktestConfig
        print("  ✓ backtesting.engine")
    except Exception as e:
        errors.append(f"backtesting.engine: {e}")
        print(f"  ✗ backtesting.engine: {e}")
    
    try:
        from risk_management import RiskManager
        print("  ✓ risk_management")
    except Exception as e:
        errors.append(f"risk_management: {e}")
        print(f"  ✗ risk_management: {e}")
    
    return len(errors) == 0, errors

def check_directories():
    """Check that required directories exist"""
    print("\nChecking directories...")
    required_dirs = ['data', 'strategies', 'backtesting', 'analysis', 'research']
    missing = []
    
    for dir_name in required_dirs:
        if os.path.exists(dir_name):
            print(f"  ✓ {dir_name}/")
        else:
            missing.append(dir_name)
            print(f"  ✗ {dir_name}/ (missing)")
    
    return len(missing) == 0, missing

def check_documentation():
    """Check that key documentation exists"""
    print("\nChecking documentation...")
    required_docs = [
        'README.md',
        'REFERENCE_INDEX.md',
        'SYSTEM_SUMMARY.md',
        'research/STRATEGY_BLUEPRINT.md'
    ]
    missing = []
    
    for doc in required_docs:
        if os.path.exists(doc):
            print(f"  ✓ {doc}")
        else:
            missing.append(doc)
            print(f"  ✗ {doc} (missing)")
    
    return len(missing) == 0, missing

def check_dependencies():
    """Check if required packages are installed"""
    print("\nChecking dependencies...")
    required_packages = [
        'ccxt',
        'pandas',
        'numpy',
        'scipy',
        'matplotlib'
    ]
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            missing.append(package)
            print(f"  ✗ {package} (not installed)")
    
    if missing:
        print(f"\n  Install missing packages: pip install {' '.join(missing)}")
    
    return len(missing) == 0, missing

def main():
    print("=" * 60)
    print("MEMECOIN PERP STRATEGIES - SETUP VERIFICATION")
    print("=" * 60)
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    all_ok = True
    
    # Check imports
    imports_ok, import_errors = check_imports()
    all_ok = all_ok and imports_ok
    
    # Check directories
    dirs_ok, dir_errors = check_directories()
    all_ok = all_ok and dirs_ok
    
    # Check documentation
    docs_ok, doc_errors = check_documentation()
    all_ok = all_ok and docs_ok
    
    # Check dependencies
    deps_ok, dep_errors = check_dependencies()
    all_ok = all_ok and deps_ok
    
    print("\n" + "=" * 60)
    if all_ok:
        print("✓ ALL CHECKS PASSED - System is ready!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Run 'python quick_start.py' for examples")
        print("2. Run 'python main.py' for full pipeline")
        print("3. Review 'REFERENCE_INDEX.md' for documentation")
        return 0
    else:
        print("✗ SOME CHECKS FAILED")
        print("=" * 60)
        if import_errors:
            print("\nImport errors:")
            for error in import_errors:
                print(f"  - {error}")
        if dir_errors:
            print("\nMissing directories:")
            for dir_name in dir_errors:
                print(f"  - {dir_name}/")
        if dep_errors:
            print("\nMissing packages:")
            print(f"  Run: pip install {' '.join(dep_errors)}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
