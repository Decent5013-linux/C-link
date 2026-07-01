import asyncio
from playwright.async_api import async_playwright
from pynput.mouse import Button, Controller
import time
import os
import subprocess
import random
import string
import math

# ===== CONFIGURATION =====
# Demo mode - if True, shows exact shifts first before doing random ones
demo = False  # Set to False for production

# Proxy settings
PROXY_SERVER = "http://127.0.0.1:3000"

# Scroll down amount (in pixels)
scroll_down = 200

# Random pixel shift before clicking (1 to this value, RIGHT only)
rand_shift = 1000

# Additional upward shift after random shift (1 to this value)
upward_shift = 40

# Additional left shift after upward shift (1 to this value)
left_after_upward = 100

# Time to wait before clicking (random between these values in milliseconds)
WAIT_BEFORE_CLICK_MIN = 35000  # 30 seconds
WAIT_BEFORE_CLICK_MAX = 60000  # 40 seconds

# Time to wait for URL change (seconds)
URL_CHANGE_TIMEOUT = 7

# Target URLs to check
BLANK_URL = "about:blank"
SURFE_PRO_URL = "surfe.pro"
SURFE_BE_URL = "surfe.be"

# Tinyproxy configuration - using local file in app directory
TINYPROXY_CONF_PATH = "tinyproxy.conf"
TINYPROXY_BINARY = "tinyproxy"

# =========================

mouse = Controller()

def generate_random_string(length=15):
    """Generate a random string of lowercase letters and numbers"""
    characters = string.ascii_lowercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def update_tinyproxy_config():
    """Update the tinyproxy configuration with a new random session ID"""
    try:
        if not os.path.exists(TINYPROXY_CONF_PATH):
            print(f"❌ Tinyproxy config not found at {TINYPROXY_CONF_PATH}")
            return False
        
        print(f"📝 Reading tinyproxy config: {TINYPROXY_CONF_PATH}")
        
        # Read the current config
        with open(TINYPROXY_CONF_PATH, 'r') as file:
            lines = file.readlines()
        
        config_updated = False
        new_lines = []
        
        for line in lines:
            # Look for the upstream line with session-
            if 'upstream http' in line and 'session-' in line:
                print(f"Found upstream line: {line.strip()}")
                
                # Split the line to find and replace the session ID
                parts = line.split('session-')
                if len(parts) >= 2:
                    after_session = parts[1]
                    colon_parts = after_session.split(':', 1)
                    
                    if len(colon_parts) >= 2:
                        # Generate new random session ID
                        new_session_id = generate_random_string()
                        
                        # Reconstruct the line with new session ID
                        new_line = parts[0] + 'session-' + new_session_id + ':' + colon_parts[1]
                        new_lines.append(new_line)
                        config_updated = True
                        
                        print(f"✓ Updated session ID to: session-{new_session_id}")
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        if config_updated:
            # Write the updated config back
            with open(TINYPROXY_CONF_PATH, 'w') as file:
                file.writelines(new_lines)
            print("✓ Configuration file updated successfully")
            return True
        else:
            print("⚠ No upstream line with session- found in config")
            return False
            
    except Exception as e:
        print(f"❌ Error updating config: {e}")
        return False

def restart_tinyproxy():
    """Kill existing tinyproxy and restart with updated config"""
    try:
        # Get absolute path for config
        config_path = os.path.abspath(TINYPROXY_CONF_PATH)
        print(f"Using config path: {config_path}")
        
        # Kill existing tinyproxy processes
        print("🔪 Killing existing tinyproxy processes...")
        subprocess.run(['pkill', 'tinyproxy'], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL)
        
        # Wait a moment for processes to die
        time.sleep(2)
        
        # Start tinyproxy with the config
        print("🚀 Starting tinyproxy with updated config...")
        subprocess.Popen([TINYPROXY_BINARY, '-d', '-c', config_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        
        # Wait for tinyproxy to initialize
        print("⏳ Waiting 10 seconds for tinyproxy to start...")
        time.sleep(10)
        
        # Verify tinyproxy is running
        result = subprocess.run(['pgrep', 'tinyproxy'], 
                              capture_output=True, 
                              text=True)
        if result.returncode == 0:
            print(f"✓ Tinyproxy running with PID: {result.stdout.strip()}")
            return True
        else:
            print("⚠ Tinyproxy may not have started correctly")
            return False
        
    except FileNotFoundError:
        print(f"❌ Tinyproxy binary not found: {TINYPROXY_BINARY}")
        return False
    except Exception as e:
        print(f"❌ Error restarting tinyproxy: {e}")
        return False

async def get_element_position(page, element):
    """Get the bounding box of an element after scrolling it into view"""
    try:
        # Scroll element into view first
        await element.scroll_into_view_if_needed()
        await asyncio.sleep(0.5)  # Wait for scroll to complete
        
        # Get the bounding box
        box = await element.bounding_box()
        if box:
            return {
                'x': box['x'] + box['width'] / 2,
                'y': box['y'] + box['height'] / 2
            }
    except Exception as e:
        print(f"Error getting element position: {e}")
    return None

async def get_page_offset(page):
    """Get the offset of the page content from screen"""
    try:
        offset = await page.evaluate('''() => {
            return {
                x: window.screenX + (window.outerWidth - window.innerWidth),
                y: window.screenY + (window.outerHeight - window.innerHeight)
            };
        }''')
        return offset
    except Exception as e:
        print(f"Error getting page offset: {e}")
        return {'x': 0, 'y': 0}

async def move_mouse_smoothly(from_x, from_y, to_x, to_y, steps=None):
    """Move mouse smoothly from one point to another"""
    if steps is None:
        steps = random.randint(8, 15)
    
    for step in range(steps):
        t = (step + 1) / steps
        curve_x = math.sin(t * math.pi) * random.randint(-5, 5)
        curve_y = math.sin(t * math.pi) * random.randint(-5, 5)
        
        intermediate_x = from_x + (to_x - from_x) * t + curve_x
        intermediate_y = from_y + (to_y - from_y) * t + curve_y
        
        mouse.position = (int(intermediate_x), int(intermediate_y))
        time.sleep(random.uniform(0.01, 0.03))
    
    mouse.position = (to_x, to_y)

async def simulate_human_behavior(page, duration_ms):
    """Simulate human-like behavior for specified duration"""
    print(f"\n🧑 Simulating human behavior for {duration_ms/1000:.1f} seconds...")
    
    start_time = time.time()
    duration_sec = duration_ms / 1000
    
    viewport = page.viewport_size
    max_x = viewport['width'] - 50
    max_y = viewport['height'] - 100
    
    offset = await get_page_offset(page)
    
    behavior_count = 0
    
    while time.time() - start_time < duration_sec:
        behavior_count += 1
        action = random.choice(['move_mouse', 'scroll', 'pause', 'small_move', 'idle'])
        
        if action == 'move_mouse':
            target_x = random.randint(100, max_x)
            target_y = random.randint(100, max_y)
            
            screen_x = offset['x'] + target_x
            screen_y = offset['y'] + target_y
            
            print(f"  🖱️  Moving mouse to ({target_x}, {target_y})")
            await move_mouse_smoothly(
                mouse.position[0], mouse.position[1],
                int(screen_x), int(screen_y),
                steps=random.randint(10, 20)
            )
            
            await asyncio.sleep(random.uniform(0.5, 2.0))
            
        elif action == 'scroll':
            scroll_amount = random.randint(-300, 300)
            direction = "down" if scroll_amount > 0 else "up"
            
            print(f"  📜 Scrolling {direction} by {abs(scroll_amount)}px")
            await page.evaluate(f'window.scrollBy(0, {scroll_amount})')
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
        elif action == 'small_move':
            jiggle_x = random.randint(-20, 20)
            jiggle_y = random.randint(-20, 20)
            
            new_screen_x = mouse.position[0] + jiggle_x
            new_screen_y = mouse.position[1] + jiggle_y
            
            print(f"  🎯 Small mouse movement ({jiggle_x:+d}, {jiggle_y:+d})")
            await move_mouse_smoothly(
                mouse.position[0], mouse.position[1],
                new_screen_x, new_screen_y,
                steps=random.randint(3, 7)
            )
            
            await asyncio.sleep(random.uniform(0.3, 1.0))
            
        elif action == 'pause':
            pause_time = random.uniform(2.0, 5.0)
            print(f"  ⏸️  Pausing for {pause_time:.1f}s")
            await asyncio.sleep(pause_time)
            
        elif action == 'idle':
            await asyncio.sleep(random.uniform(0.1, 0.5))
        
        elapsed = time.time() - start_time
        if elapsed >= duration_sec:
            break
        
        await asyncio.sleep(random.uniform(0.1, 0.3))
    
    print(f"  ✅ Human behavior simulation complete ({behavior_count} actions)")

async def reacquire_element(page, element_text):
    """Re-find the element after human behavior simulation"""
    print(f"\n🔍 Re-finding element with text: '{element_text}'...")
    
    try:
        # Find the element again by its text content
        element_handle = await page.evaluate_handle(f'''() => {{
            const sbts = document.querySelectorAll('sbt.sbt-domain__text');
            const visibleSbts = Array.from(sbts).filter(sbt => 
                sbt.offsetParent !== null && 
                sbt.textContent.trim() === '{element_text}'
            );
            return visibleSbts[0] || null;
        }}''')
        
        element = element_handle.as_element()
        if element:
            # Scroll the element into view
            await element.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            
            # Verify it's still visible
            is_visible = await element.is_visible()
            if is_visible:
                print(f"✓ Element found and scrolled into view")
                return element
            else:
                print(f"⚠ Element found but not visible")
                return None
        else:
            print(f"❌ Element not found after simulation")
            return None
            
    except Exception as e:
        print(f"Error re-finding element: {e}")
        return None

async def perform_random_shifts(page, element):
    """Perform the actual random shifts and click"""
    try:
        # Get fresh element position after scrolling into view
        position = await get_element_position(page, element)
        if not position:
            print("Could not get element position after scroll")
            return False
        
        # Get page offset
        offset = await get_page_offset(page)
        
        # Calculate base screen coordinates
        base_x = offset['x'] + position['x']
        base_y = offset['y'] + position['y']
        
        print(f"\n📍 Element position after scroll: ({int(position['x'])}, {int(position['y'])})")
        print(f"   Screen coordinates: ({int(base_x)}, {int(base_y)})")
        
        # Move mouse to element center first
        print(f"Moving mouse to element center...")
        await move_mouse_smoothly(mouse.position[0], mouse.position[1], int(base_x), int(base_y))
        await asyncio.sleep(0.5)
        
        # Step 1: Random shift RIGHT only
        random_offset_x = random.randint(1, rand_shift)
        random_offset_y = 0
        
        after_random_x = base_x + random_offset_x
        after_random_y = base_y + random_offset_y
        
        print(f"Step 1 - Random shift RIGHT (1-{rand_shift}px): +{random_offset_x}")
        await move_mouse_smoothly(int(base_x), int(base_y), int(after_random_x), int(after_random_y))
        await asyncio.sleep(0.3)
        
        # Step 2: Upward shift
        upward_offset = random.randint(1, upward_shift)
        after_upward_x = after_random_x
        after_upward_y = after_random_y - upward_offset
        
        print(f"Step 2 - Upward shift (1-{upward_shift}px): -{upward_offset}")
        await move_mouse_smoothly(int(after_random_x), int(after_random_y), int(after_upward_x), int(after_upward_y))
        await asyncio.sleep(0.3)
        
        # Step 3: Left shift
        left_offset = random.randint(1, left_after_upward)
        final_x = int(after_upward_x - left_offset)
        final_y = int(after_upward_y)
        
        print(f"Step 3 - Left shift (1-{left_after_upward}px): -{left_offset}")
        await move_mouse_smoothly(int(after_upward_x), int(after_upward_y), final_x, final_y)
        await asyncio.sleep(0.3)
        
        print(f"Final position: ({final_x}, {final_y})")
        print(f"Total offset from center: ({final_x - int(base_x):+d}, {final_y - int(base_y):+d})")
        
        # Verify element is still there before clicking
        is_visible = await element.is_visible()
        if not is_visible:
            print("⚠ Element no longer visible, re-scrolling into view...")
            await element.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
        
        # Click
        mouse.click(Button.left, 1)
        print("✓ Clicked element")
        await asyncio.sleep(0.5)
        
        return True
    except Exception as e:
        print(f"Error in random shifts: {e}")
        return False

async def click_sbt_element(page, index, element_text):
    """Click on a specific sbt element with human behavior simulation"""
    try:
        # First, get the initial element
        element_handle = await page.evaluate_handle(f'''() => {{
            const sbts = document.querySelectorAll('sbt.sbt-domain__text');
            const visibleSbts = Array.from(sbts).filter(sbt => sbt.offsetParent !== null);
            return visibleSbts[{index}];
        }}''')
        
        element = element_handle.as_element()
        if not element:
            print("Could not get initial element")
            return False
        
        # Perform human behavior simulation
        wait_time = random.randint(WAIT_BEFORE_CLICK_MIN, WAIT_BEFORE_CLICK_MAX)
        print(f"\n⏰ Waiting {wait_time/1000:.1f} seconds with human-like behavior before clicking...")
        await simulate_human_behavior(page, wait_time)
        
        # Re-acquire the element after simulation (page may have scrolled/changed)
        element = await reacquire_element(page, element_text)
        if not element:
            print("❌ Failed to re-acquire element after simulation")
            return False
        
        # Perform the click with random shifts
        return await perform_random_shifts(page, element)
            
    except Exception as e:
        print(f"Error clicking element: {e}")
        return False

async def find_sbt_domain_elements(page):
    """Find all <sbt class='sbt-domain__text'> elements with their text content"""
    elements = await page.evaluate('''() => {
        const sbts = document.querySelectorAll('sbt.sbt-domain__text');
        return Array.from(sbts).map((sbt, index) => {
            return {
                index: index,
                text: sbt.textContent.trim(),
                innerHTML: sbt.innerHTML.trim(),
                visible: sbt.offsetParent !== null,
                hasLink: sbt.querySelector('a') !== null
            };
        });
    }''')
    return elements

async def wait_for_url_change(popup, timeout):
    """Wait for popup URL to change and check against target URLs"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            current_url = popup.url.lower()
            print(f"  Current popup URL: {current_url}")
            
            if SURFE_BE_URL in current_url:
                print(f"  ✓ URL contains {SURFE_BE_URL}")
                return "surfe_be"
            
            if current_url == BLANK_URL or SURFE_PRO_URL in current_url:
                await asyncio.sleep(0.5)
                continue
            else:
                print(f"  URL changed to: {current_url}")
                return "other_url"
                
        except Exception as e:
            print(f"  Error checking popup URL: {e}")
            break
        
        await asyncio.sleep(0.5)
    
    return "timeout"

async def main():
    # ===== PRE-LAUNCH: Update tinyproxy config =====
    print("="*60)
    print("PRE-LAUNCH: Configuring tinyproxy")
    print("="*60)
    
    worker_id = os.environ.get('WORKER_ID', 'unknown')
    print(f"Worker ID: {worker_id}")
    
    print(f"⏰ Wait before click: {WAIT_BEFORE_CLICK_MIN/1000}-{WAIT_BEFORE_CLICK_MAX/1000} seconds")
    print(f"   with human-like behavior simulation")
    print()
    
    if not update_tinyproxy_config():
        print("⚠ Continuing without updating config...")
    
    if not restart_tinyproxy():
        print("⚠ Failed to restart tinyproxy, continuing anyway...")
    
    print("\n" + "="*60)
    print("STARTING BROWSER AUTOMATION")
    print("="*60 + "\n")
    
    # ===== BROWSER AUTOMATION =====
    async with async_playwright() as p:
        # Launch browser with proxy
        browser = await p.chromium.launch(
            headless=False,
            proxy={
                "server": PROXY_SERVER
            },
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = await context.new_page()
        
        popup_pages = []
        
        async def handle_popup(popup):
            print(f"\n📌 New popup window detected!")
            popup_pages.append(popup)
            
        context.on('page', handle_popup)
        
        try:
            print(f"Navigating to https://fconverter.vipb.top/mp4-to-avi.php")
            await page.goto('https://fconverter.vipb.top/mp4-to-avi.php', wait_until='load')
            
            await page.wait_for_load_state('networkidle')
            print("Page loaded successfully")
            
            print(f"Scrolling down {scroll_down} pixels...")
            await page.evaluate(f'window.scrollBy(0, {scroll_down})')
            await asyncio.sleep(1)
            
            max_attempts = 10
            attempt = 0
            sbt_elements = []
            
            while attempt < max_attempts and len(sbt_elements) == 0:
                sbt_elements = await find_sbt_domain_elements(page)
                
                if len(sbt_elements) == 0:
                    print(f"No sbt domain elements found. Attempt {attempt + 1}/{max_attempts}")
                    await asyncio.sleep(2)
                    await page.evaluate(f'window.scrollBy(0, 100)')
                    await asyncio.sleep(1)
                    attempt += 1
            
            if len(sbt_elements) == 0:
                print("❌ No sbt domain elements found after maximum attempts")
                return
            
            print(f"\n✓ Found {len(sbt_elements)} sbt domain elements:")
            for elem in sbt_elements:
                print(f"  [{elem['index']}] Text: '{elem['text']}' | Visible: {elem['visible']}")
            
            non_surfe_elements = [
                elem for elem in sbt_elements 
                if elem['visible'] and SURFE_BE_URL not in elem['text'].lower()
            ]
            
            print(f"\n✓ Found {len(non_surfe_elements)} non-surfe.be elements to click:")
            for elem in non_surfe_elements:
                print(f"  [{elem['index']}] Text: '{elem['text']}'")
            
            # Process each non-surfe.be element
            for i, element_info in enumerate(non_surfe_elements):
                print(f"\n{'='*50}")
                print(f"Processing element {i + 1}/{len(non_surfe_elements)}")
                print(f"Element text: '{element_info['text']}'")
                print(f"{'='*50}")
                
                old_popup_count = len(popup_pages)
                
                # Re-find elements (page might have changed)
                current_elements = await find_sbt_domain_elements(page)
                current_non_surfe = [
                    elem for elem in current_elements 
                    if elem['visible'] and SURFE_BE_URL not in elem['text'].lower()
                ]
                
                if i >= len(current_non_surfe):
                    print(f"Element {i} no longer available")
                    continue
                
                # Click the element (includes wait with human behavior and re-acquisition)
                original_index = current_non_surfe[i]['index']
                element_text = current_non_surfe[i]['text']
                print(f"Clicking element with text: '{element_text}'")
                
                click_success = await click_sbt_element(page, original_index, element_text)
                
                if not click_success:
                    print(f"⚠ Failed to click element")
                    continue
                
                await asyncio.sleep(2)
                
                if len(popup_pages) > old_popup_count:
                    popup = popup_pages[-1]
                    print(f"New popup window opened")
                    
                    result = await wait_for_url_change(popup, URL_CHANGE_TIMEOUT)
                    
                    if result == "surfe_be":
                        print(f"✓ URL is surfe.be - Closing popup and continuing")
                        await popup.close()
                        popup_pages.pop()
                    elif result == "other_url":
                        print(f"❌ URL is not surfe.be - Closing browser in 7 seconds")
                        await asyncio.sleep(7)
                        await browser.close()
                        return
                    else:
                        print(f"⚠ Timeout - URL didn't change within {URL_CHANGE_TIMEOUT} seconds")
                        try:
                            await popup.close()
                            popup_pages.pop()
                        except:
                            pass
                else:
                    print(f"⚠ No popup window detected for this element")
                
                await asyncio.sleep(1)
            
            print(f"\n✓ All non-surfe.be elements processed successfully")
            
        except Exception as e:
            print(f"An error occurred: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            print(f"\nWaiting 5 seconds before closing...")
            await asyncio.sleep(5)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
