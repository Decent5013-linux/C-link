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
demo = False  # Set to True to demo the shifts, False for normal operation

# Proxy settings
PROXY_SERVER = "http://127.0.0.1:3000"

# Scroll down amount (in pixels)
scroll_down = 200  # Adjust this value as needed

# Random pixel shift before clicking (1 to this value, RIGHT only)
rand_shift = 1000  # Mouse will shift 1 to rand_shift pixels RIGHT before clicking

# Additional upward shift after random shift (1 to this value)
upward_shift = 40  # Mouse will shift upward 1 to upward_shift pixels after random shift

# Additional left shift after upward shift (1 to this value)
left_after_upward = 100  # Mouse will shift left 1 to left_after_upward pixels after upward shift

# Time to wait before clicking (random between these values in milliseconds)
WAIT_BEFORE_CLICK_MIN = 30000  # 30 seconds
WAIT_BEFORE_CLICK_MAX = 60000  # 40 seconds

# Time to wait for URL change (seconds)
URL_CHANGE_TIMEOUT = 7

# Target URLs to check
BLANK_URL = "about:blank"
SURFE_PRO_URL = "surfe.pro"
SURFE_BE_URL = "surfe.be"

# Tinyproxy configuration
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
                # Pattern: upstream http ...session-<old_string>:...
                parts = line.split('session-')
                if len(parts) >= 2:
                    # Get the part after 'session-'
                    after_session = parts[1]
                    # Split at ':' to separate the session ID from the rest
                    colon_parts = after_session.split(':', 1)
                    
                    if len(colon_parts) >= 2:
                        # Generate new random session ID
                        new_session_id = generate_random_string()
                        
                        # Reconstruct the line with new session ID
                        new_line = parts[0] + 'session-' + new_session_id + ':' + colon_parts[1]
                        new_lines.append(new_line)
                        config_updated = True
                        
                        print(f"✓ Updated session ID to: session-{new_session_id}")
                        print(f"New line: {new_line.strip()}")
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
            
    except FileNotFoundError:
        print(f"❌ Config file not found: {TINYPROXY_CONF_PATH}")
        return False
    except PermissionError:
        print(f"❌ Permission denied. Try running with sudo")
        return False
    except Exception as e:
        print(f"❌ Error updating config: {e}")
        return False

def restart_tinyproxy():
    """Kill existing tinyproxy and restart with updated config"""
    try:
        # Kill existing tinyproxy processes
        print("🔪 Killing existing tinyproxy processes...")
        subprocess.run(['pkill', 'tinyproxy'], 
                      stdout=subprocess.DEVNULL, 
                      stderr=subprocess.DEVNULL)
        
        # Wait a moment for processes to die
        time.sleep(1)
        
        # Start tinyproxy with the config
        print("🚀 Starting tinyproxy with updated config...")
        subprocess.Popen([TINYPROXY_BINARY, '-c', TINYPROXY_CONF_PATH],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        
        # Wait for tinyproxy to initialize (10 seconds)
        print("⏳ Waiting 10 seconds for tinyproxy to start...")
        time.sleep(10)
        
        print("✓ Tinyproxy restarted successfully")
        return True
        
    except FileNotFoundError:
        print(f"❌ Tinyproxy binary not found: {TINYPROXY_BINARY}")
        print("Make sure tinyproxy is installed and in PATH")
        return False
    except Exception as e:
        print(f"❌ Error restarting tinyproxy: {e}")
        return False

async def get_element_position(page, element):
    """Get the bounding box of an element"""
    try:
        box = await element.bounding_box()
        if box:
            # Return center of element
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
        # Add slight curve to movement
        curve_x = math.sin(t * math.pi) * random.randint(-5, 5)
        curve_y = math.sin(t * math.pi) * random.randint(-5, 5)
        
        intermediate_x = from_x + (to_x - from_x) * t + curve_x
        intermediate_y = from_y + (to_y - from_y) * t + curve_y
        
        mouse.position = (int(intermediate_x), int(intermediate_y))
        time.sleep(random.uniform(0.01, 0.03))
    
    # Ensure we end exactly at the target
    mouse.position = (to_x, to_y)

async def simulate_human_behavior(page, duration_ms):
    """Simulate human-like behavior for specified duration"""
    print(f"\n🧑 Simulating human behavior for {duration_ms/1000:.1f} seconds...")
    
    start_time = time.time()
    duration_sec = duration_ms / 1000
    
    # Get viewport dimensions for mouse movement bounds
    viewport = page.viewport_size
    max_x = viewport['width'] - 50
    max_y = viewport['height'] - 100
    
    # Get page offset for screen coordinates
    offset = await get_page_offset(page)
    
    # Random initial position
    current_mouse_x = random.randint(100, max_x)
    current_mouse_y = random.randint(100, max_y)
    
    behavior_count = 0
    
    while time.time() - start_time < duration_sec:
        behavior_count += 1
        action = random.choice(['move_mouse', 'scroll', 'pause', 'small_move', 'idle'])
        
        if action == 'move_mouse':
            # Move mouse to a random position on the page
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
            
            current_mouse_x = target_x
            current_mouse_y = target_y
            
            # Random pause after moving
            await asyncio.sleep(random.uniform(0.5, 2.0))
            
        elif action == 'scroll':
            # Random scroll up or down
            scroll_amount = random.randint(-300, 300)
            direction = "down" if scroll_amount > 0 else "up"
            
            print(f"  📜 Scrolling {direction} by {abs(scroll_amount)}px")
            await page.evaluate(f'window.scrollBy(0, {scroll_amount})')
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
        elif action == 'small_move':
            # Small mouse jiggle
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
            # Random pause
            pause_time = random.uniform(2.0, 5.0)
            print(f"  ⏸️  Pausing for {pause_time:.1f}s")
            await asyncio.sleep(pause_time)
            
        elif action == 'idle':
            # Very brief idle
            await asyncio.sleep(random.uniform(0.1, 0.5))
        
        # Check if we've exceeded the duration
        elapsed = time.time() - start_time
        if elapsed >= duration_sec:
            break
        
        # Random small delay between actions
        await asyncio.sleep(random.uniform(0.1, 0.3))
    
    print(f"  ✅ Human behavior simulation complete ({behavior_count} actions)")

async def demo_shifts(page, element):
    """Demo mode: Show exact shifts at specified values with 5 second waits"""
    try:
        print("\n" + "="*60)
        print("🎯 DEMO MODE - Showing exact shifts")
        print("="*60)
        
        # Get element position
        position = await get_element_position(page, element)
        if not position:
            print("Could not get element position")
            return False
        
        # Get page offset
        offset = await get_page_offset(page)
        
        # Calculate base screen coordinates
        base_x = offset['x'] + position['x']
        base_y = offset['y'] + position['y']
        
        print(f"\nElement center position: ({int(position['x'])}, {int(position['y'])})")
        print(f"Starting mouse position: ({int(base_x)}, {int(base_y)})")
        
        # Move mouse to element center first
        print(f"\n📍 Moving mouse to element center...")
        await move_mouse_smoothly(mouse.position[0], mouse.position[1], int(base_x), int(base_y))
        await asyncio.sleep(1)
        
        # Step 1: Show exact rand_shift (1000 pixels RIGHT only)
        print(f"\n📐 DEMO Step 1: Moving exactly {rand_shift} pixels RIGHT...")
        demo_x1 = int(base_x) + rand_shift
        demo_y1 = int(base_y)
        await move_mouse_smoothly(int(base_x), int(base_y), demo_x1, demo_y1)
        print(f"  Moved to: ({demo_x1}, {demo_y1}) - Exactly {rand_shift}px right")
        await asyncio.sleep(5)
        
        # Step 2: Show exact upward_shift (40 pixels up)
        print(f"\n📐 DEMO Step 2: Moving exactly {upward_shift} pixels UPWARD...")
        demo_x2 = demo_x1
        demo_y2 = demo_y1 - upward_shift
        await move_mouse_smoothly(demo_x1, demo_y1, demo_x2, demo_y2)
        print(f"  Moved to: ({demo_x2}, {demo_y2}) - Exactly {upward_shift}px up")
        await asyncio.sleep(5)
        
        # Step 3: Show exact left_after_upward (100 pixels left)
        print(f"\n📐 DEMO Step 3: Moving exactly {left_after_upward} pixels LEFT...")
        demo_x3 = demo_x2 - left_after_upward
        demo_y3 = demo_y2
        await move_mouse_smoothly(demo_x2, demo_y2, demo_x3, demo_y3)
        print(f"  Moved to: ({demo_x3}, {demo_y3}) - Exactly {left_after_upward}px left")
        await asyncio.sleep(5)
        
        # Step 4: Wait with human behavior before clicking
        wait_time = random.randint(WAIT_BEFORE_CLICK_MIN, WAIT_BEFORE_CLICK_MAX)
        print(f"\n⏰ Waiting {wait_time/1000:.1f} seconds with human-like behavior before clicking...")
        await simulate_human_behavior(page, wait_time)
        
        # Step 5: Now do the random shifts
        print(f"\n🎲 Now doing actual random shifts...")
        await perform_random_shifts(base_x, base_y)
        
        return True
    except Exception as e:
        print(f"Error in demo shifts: {e}")
        return False

async def perform_random_shifts(base_x, base_y):
    """Perform the actual random shifts and click"""
    try:
        # Return to element center first
        print(f"\n📍 Returning to element center: ({int(base_x)}, {int(base_y)})")
        await move_mouse_smoothly(mouse.position[0], mouse.position[1], int(base_x), int(base_y))
        await asyncio.sleep(0.5)
        
        # Step 1: Random shift RIGHT only (1 to rand_shift pixels)
        random_offset_x = random.randint(1, rand_shift)  # RIGHT only, always positive
        random_offset_y = 0  # No vertical movement in this step
        
        after_random_x = base_x + random_offset_x
        after_random_y = base_y + random_offset_y
        
        print(f"Step 1 - Random shift RIGHT (1-{rand_shift}px): +{random_offset_x}")
        await move_mouse_smoothly(int(base_x), int(base_y), int(after_random_x), int(after_random_y))
        await asyncio.sleep(0.3)
        
        # Step 2: Upward shift (1 to upward_shift pixels) - only upward direction
        upward_offset = random.randint(1, upward_shift)
        after_upward_x = after_random_x
        after_upward_y = after_random_y - upward_offset
        
        print(f"Step 2 - Upward shift (1-{upward_shift}px): -{upward_offset}")
        await move_mouse_smoothly(int(after_random_x), int(after_random_y), int(after_upward_x), int(after_upward_y))
        await asyncio.sleep(0.3)
        
        # Step 3: Left shift (1 to left_after_upward pixels) - only left direction
        left_offset = random.randint(1, left_after_upward)
        final_x = int(after_upward_x - left_offset)
        final_y = int(after_upward_y)
        
        print(f"Step 3 - Left shift (1-{left_after_upward}px): -{left_offset}")
        await move_mouse_smoothly(int(after_upward_x), int(after_upward_y), final_x, final_y)
        await asyncio.sleep(0.3)
        
        print(f"Final position: ({final_x}, {final_y})")
        print(f"Total offset from center: ({final_x - int(base_x):+d}, {final_y - int(base_y):+d})")
        
        # Click
        mouse.click(Button.left, 1)
        print("✓ Clicked element")
        await asyncio.sleep(0.5)
        
        return True
    except Exception as e:
        print(f"Error in random shifts: {e}")
        return False

async def move_mouse_with_random_offset(page, element):
    """Move mouse to element with multiple random pixel shifts before clicking"""
    try:
        # Get element position
        position = await get_element_position(page, element)
        if not position:
            print("Could not get element position")
            return False
        
        # Get page offset
        offset = await get_page_offset(page)
        
        # Calculate base screen coordinates
        base_x = offset['x'] + position['x']
        base_y = offset['y'] + position['y']
        
        print(f"\nElement center position: ({int(position['x'])}, {int(position['y'])})")
        
        if demo:
            # Demo mode: Show exact shifts first
            return await demo_shifts(page, element)
        else:
            # Normal mode: Wait with human behavior then do random shifts
            wait_time = random.randint(WAIT_BEFORE_CLICK_MIN, WAIT_BEFORE_CLICK_MAX)
            print(f"\n⏰ Waiting {wait_time/1000:.1f} seconds with human-like behavior before clicking...")
            await simulate_human_behavior(page, wait_time)
            return await perform_random_shifts(base_x, base_y)
            
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

async def click_sbt_element(page, index):
    """Click on a specific sbt element by its index"""
    try:
        # Get all visible sbt elements
        element_handle = await page.evaluate_handle(f'''() => {{
            const sbts = document.querySelectorAll('sbt.sbt-domain__text');
            const visibleSbts = Array.from(sbts).filter(sbt => sbt.offsetParent !== null);
            return visibleSbts[{index}];
        }}''')
        
        element = element_handle.as_element()
        if element:
            return await move_mouse_with_random_offset(page, element)
        return False
    except Exception as e:
        print(f"Error getting sbt element: {e}")
        return False

async def wait_for_url_change(popup, timeout):
    """Wait for popup URL to change and check against target URLs"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            current_url = popup.url.lower()
            print(f"  Current popup URL: {current_url}")
            
            # Check if URL contains surfe.be
            if SURFE_BE_URL in current_url:
                print(f"  ✓ URL contains {SURFE_BE_URL}")
                return "surfe_be"
            
            # Check if URL is still blank or surfe.pro
            if current_url == BLANK_URL or SURFE_PRO_URL in current_url:
                await asyncio.sleep(0.5)
                continue
            else:
                # URL changed to something else
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
    
    if demo:
        print("\n🎯 DEMO MODE ENABLED")
        print("The mouse will show exact shifts before doing random ones:")
        print(f"  - rand_shift: {rand_shift}px RIGHT")
        print(f"  - upward_shift: {upward_shift}px UP")
        print(f"  - left_after_upward: {left_after_upward}px LEFT")
        print("Each demo step will wait 5 seconds")
        print()
    
    print(f"⏰ Wait before click: {WAIT_BEFORE_CLICK_MIN/1000}-{WAIT_BEFORE_CLICK_MAX/1000} seconds")
    print(f"   with human-like behavior simulation")
    print()
    
    if not update_tinyproxy_config():
        print("⚠ Continuing without updating config...")
    
    if not restart_tinyproxy():
        print("⚠ Failed to restart tinyproxy, but continuing...")
    
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
            }
        )
        
        # Create context
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720}
        )
        
        # Create main page
        page = await context.new_page()
        
        # Set to listen for new pages (popups)
        popup_pages = []
        
        async def handle_popup(popup):
            print(f"\n📌 New popup window detected!")
            popup_pages.append(popup)
            
        context.on('page', handle_popup)
        
        try:
            # Navigate to the URL
            print(f"Navigating to https://fconverter.vipb.top/mp4-to-avi.php")
            await page.goto('https://fconverter.vipb.top/mp4-to-avi.php', wait_until='load')
            
            # Wait for page to fully load
            await page.wait_for_load_state('networkidle')
            print("Page loaded successfully")
            
            # Scroll down
            print(f"Scrolling down {scroll_down} pixels...")
            await page.evaluate(f'window.scrollBy(0, {scroll_down})')
            await asyncio.sleep(1)
            
            # Keep checking for sbt domain elements (they might load dynamically)
            max_attempts = 10
            attempt = 0
            sbt_elements = []
            
            while attempt < max_attempts and len(sbt_elements) == 0:
                # Find all sbt domain elements
                sbt_elements = await find_sbt_domain_elements(page)
                
                if len(sbt_elements) == 0:
                    print(f"No sbt domain elements found. Attempt {attempt + 1}/{max_attempts}")
                    await asyncio.sleep(2)
                    # Try scrolling a bit more
                    await page.evaluate(f'window.scrollBy(0, 100)')
                    await asyncio.sleep(1)
                    attempt += 1
            
            if len(sbt_elements) == 0:
                print("❌ No sbt domain elements found after maximum attempts")
                return
            
            print(f"\n✓ Found {len(sbt_elements)} sbt domain elements:")
            for elem in sbt_elements:
                print(f"  [{elem['index']}] Text: '{elem['text']}' | Visible: {elem['visible']}")
            
            # Filter elements that are NOT surfe.be
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
                
                # Clear previous popups tracking
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
                
                # Click the element (includes wait with human behavior)
                original_index = current_non_surfe[i]['index']
                print(f"Clicking element with text: '{current_non_surfe[i]['text']}'")
                
                click_success = await click_sbt_element(page, original_index)
                
                if not click_success:
                    print(f"⚠ Failed to click element")
                    continue
                
                # Wait for popup to appear
                await asyncio.sleep(2)
                
                # Check if new popup appeared
                if len(popup_pages) > old_popup_count:
                    popup = popup_pages[-1]
                    print(f"New popup window opened")
                    
                    # Wait for URL change and check
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
                        # Close the popup anyway
                        try:
                            await popup.close()
                            popup_pages.pop()
                        except:
                            pass
                else:
                    print(f"⚠ No popup window detected for this element")
                
                # Small delay between processing elements
                await asyncio.sleep(1)
            
            print(f"\n✓ All non-surfe.be elements processed successfully")
            
        except Exception as e:
            print(f"An error occurred: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Keep browser open for a moment
            print(f"\nWaiting 5 seconds before closing...")
            await asyncio.sleep(5)
            await browser.close()

if __name__ == "__main__":
    # Check if running with appropriate permissions
    if os.geteuid() != 0:
        print("⚠ WARNING: This script needs root privileges to edit /etc/tinyproxy/tinyproxy.conf")
        print("⚠ Please run with: sudo python script.py")
        print()
    
    asyncio.run(main())
