from price_checker import KalshiPriceChecker
import json

print('Testing price_checker directly...\n')

pc = KalshiPriceChecker(demo_mode=False)  # Will use default: https://api.elections.kalshi.com
print(f'Base URL: {pc.base_url}')
print(f'API Base: {pc.api_base}')
print(f'Ticker: KXSENATEMED-26-GRA')
print(f'Side: yes\n')

try:
    result = pc.get_current_price('KXSENATEMED-26-GRA', 'yes')
    print(f'\nResult: {result}')
except Exception as e:
    print(f'\nException: {e}')
    import traceback
    traceback.print_exc()

