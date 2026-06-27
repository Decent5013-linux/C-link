import asyncio
import random
import subprocess
import re
from patchright.async_api import async_playwright
from pynput.mouse import Button, Controller as MouseController
import time
import math

# MODE: 0 = fetch random UA/viewport, 1 = use system defaults (90% mobile, 10% system)
MODE = 1

# Initialize mouse controller
mouse = MouseController()

async def get_random_user_agent():
    """Fetch random user agent and viewport from the API"""
    try:
        # 80% mobile, 20% desktop
        if random.random() < 0.8:
            endpoint = "fconverter.vipb.top/mobile.txt"
            is_mobile = True
        else:
            endpoint = "fconverter.vipb.top/desktop.txt"
            is_mobile = False
        
        # Execute curl command with 30 second timeout
        result = subprocess.run(
            ['curl', '-s', '--max-time', '30', endpoint],
            capture_output=True,
            text=True,
            timeout=35
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            raise Exception(f"Curl failed with return code {result.returncode}")
        
        lines = result.stdout.strip().split('\n')
        if not lines:
            raise Exception("No lines returned from API")
        
        # Select random line
        random_line = random.choice(lines)
        
        # Parse user agent and viewport
        parts = random_line.strip().split('|')
        if len(parts) != 2:
            raise Exception(f"Invalid format: {random_line}")
        
        user_agent = parts[0]
        viewport = parts[1].split('x')
        viewport_width = int(viewport[0])
        viewport_height = int(viewport[1])
        
        return user_agent, viewport_width, viewport_height, is_mobile
    except Exception as e:
        print(f"Error fetching user agent: {e}")
        if random.random() < 0.8:
            return "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Mobile Safari/537.36", 412, 915, True
        else:
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36", 1920, 1080, False

def is_cpmlink_url(url):
    """Check if URL belongs to cpmlink domain (any TLD)"""
    return bool(re.search(r'cpmlink\.', url))

def is_target_url(url):
    """Check if URL is one of the target URLs"""
    return "bildirim.online" in url or "telead.mail.name.ng" in url

def should_keep_page(url):
    """Check if a page should be kept (not closed)"""
    if not url or url == "about:blank":
        return True
    
    if is_cpmlink_url(url):
        return True
    
    if is_target_url(url):
        return True
    
    return False

def move_mouse_to_target(target_x, target_y):
    """Move mouse straight to target with natural speed"""
    current_x, current_y = mouse.position
    
    distance = math.sqrt((target_x - current_x)**2 + (target_y - current_y)**2)
    
    if distance < 100:
        duration = random.uniform(0.2, 0.35)
    elif distance < 300:
        duration = random.uniform(0.3, 0.5)
    elif distance < 600:
        duration = random.uniform(0.4, 0.65)
    else:
        duration = random.uniform(0.5, 0.8)
    
    steps = max(20, int(duration * 100))
    
    for i in range(steps + 1):
        t = i / steps
        
        if t < 0.5:
            eased_t = 2 * t * t
        else:
            eased_t = -1 + (4 - 2 * t) * t
        
        x = current_x + (target_x - current_x) * eased_t
        y = current_y + (target_y - current_y) * eased_t
        
        mouse.position = (int(x), int(y))
        time.sleep(duration / steps)
    
    mouse.position = (int(target_x), int(target_y))
    time.sleep(0.05)

def click_mouse():
    """Simple mouse click"""
    time.sleep(random.uniform(0.05, 0.1))
    mouse.click(Button.left, 1)
    time.sleep(random.uniform(0.03, 0.06))

async def get_screen_coordinates(page, viewport_x, viewport_y):
    """Convert viewport coordinates to screen coordinates"""
    try:
        pos = await page.evaluate("""
            () => {
                return {
                    screenX: window.screenX || 0,
                    screenY: window.screenY || 0,
                    outerWidth: window.outerWidth,
                    innerWidth: window.innerWidth,
                    outerHeight: window.outerHeight,
                    innerHeight: window.innerHeight
                };
            }
        """)
        
        chrome_width = (pos['outerWidth'] - pos['innerWidth']) / 2
        chrome_height = pos['outerHeight'] - pos['innerHeight'] - chrome_width
        
        screen_x = pos['screenX'] + chrome_width + viewport_x
        screen_y = pos['screenY'] + chrome_height + viewport_y
        
        return screen_x, screen_y
    except:
        return viewport_x + 8, viewport_y + 80

async def block_mousemove_detection(page):
    """Block mousemove event listeners from detecting mouse movement"""
    try:
        await page.evaluate("""
            () => {
                const originalAddEventListener = EventTarget.prototype.addEventListener;
                EventTarget.prototype.addEventListener = function(type, listener, options) {
                    if (type === 'mousemove') {
                        return;
                    }
                    return originalAddEventListener.call(this, type, listener, options);
                };
                
                document.querySelectorAll('*').forEach(el => {
                    el.onmousemove = null;
                });
                document.onmousemove = null;
                window.onmousemove = null;
            }
        """)
        print("Mouse movement detection blocked")
    except Exception as e:
        print(f"Error blocking mousemove: {e}")

async def handle_turnstile(page, is_mobile):
    """Handle .cf-turnstile - click repeatedly until token response detected"""
    try:
        has_click_continue = await check_for_element_simple(page, 'button.confirm', timeout=500)
        if has_click_continue:
            return
        
        turnstile = page.locator(".cf-turnstile")
        turnstile_count = await turnstile.count()
        
        if turnstile_count > 0:
            print("Turnstile detected!")
            
            if is_mobile:
                await block_mousemove_detection(page)
            
            box = await turnstile.bounding_box()
            if not box:
                return
            
            offset = await page.evaluate("""
                () => ({
                    x: window.screenX || 0,
                    y: window.screenY + (window.outerHeight - window.innerHeight) || 0
                })
            """)
            
            initial_x = offset['x'] + box['x'] + (box['width'] / 2)
            initial_y = offset['y'] + box['y'] + (box['height'] / 2)
            
            max_clicks = 20
            for click_num in range(max_clicks):
                print(f"Turnstile click {click_num + 1}")
                
                mouse.position = (int(initial_x), int(initial_y))
                time.sleep(0.1)
                
                move_left = random.randint(20, 40)
                mouse.move(-move_left, 0)
                time.sleep(0.05)
                
                move_left_again = random.randint(10, 20)
                mouse.move(-move_left_again, 0)
                time.sleep(0.05)
                
                if is_mobile:
                    mouse.move(0, 100)
                    time.sleep(0.05)
                
                mouse.click(Button.left)
                
                await asyncio.sleep(0.5)
                
                still_exists = await turnstile.count()
                if still_exists == 0:
                    print("Turnstile solved!")
                    return
                
                has_token = await page.evaluate("""
                    () => {
                        return document.querySelector('[data-token]') !== null ||
                               document.querySelector('.complete') !== null ||
                               document.querySelector('main#main') !== null;
                    }
                """)
                
                if has_token:
                    print("Token response detected!")
                    return
            
            print("Turnstile handling completed")
                
    except Exception as e:
        print(f"Error handling turnstile: {e}")

async def check_countdown(page):
    """Check if there's a countdown and wait for it to complete"""
    try:
        countdown_status = await page.evaluate("""
            () => {
                const complete = document.querySelector('.countdown .complete');
                if (complete) {
                    const style = window.getComputedStyle(complete);
                    if (style.display === 'block') {
                        return 'complete';
                    }
                }
                
                const timeElem = document.querySelector('.countdown .time strong');
                if (timeElem) {
                    const seconds = parseInt(timeElem.textContent);
                    if (!isNaN(seconds)) {
                        return seconds;
                    }
                }
                
                return null;
            }
        """)
        
        if countdown_status is None:
            return True
        
        if countdown_status == 'complete':
            return True
        
        if isinstance(countdown_status, int):
            print(f"Countdown at {countdown_status}s, waiting...")
            
            for _ in range(30):
                await asyncio.sleep(1)
                
                new_status = await page.evaluate("""
                    () => {
                        const complete = document.querySelector('.countdown .complete');
                        if (complete && window.getComputedStyle(complete).display === 'block') {
                            return 'complete';
                        }
                        
                        const timeElem = document.querySelector('.countdown .time strong');
                        if (timeElem) {
                            const seconds = parseInt(timeElem.textContent);
                            if (!isNaN(seconds)) {
                                return seconds;
                            }
                        }
                        
                        return 'unknown';
                    }
                """)
                
                if new_status == 'complete':
                    await asyncio.sleep(1)
                    return True
                
                if isinstance(new_status, int):
                    print(f"Countdown: {new_status}s")
        
        return True
        
    except Exception as e:
        print(f"Error checking countdown: {e}")
        return True

async def click_element_at_position(page, selector, is_mobile):
    """Click element - mouse for desktop, touch for mobile"""
    try:
        element = await page.wait_for_selector(selector, state='attached', timeout=5000)
        await element.scroll_into_view_if_needed()
        time.sleep(0.2)
        
        box = await element.bounding_box()
        if not box:
            try:
                if is_mobile:
                    await page.touchscreen.tap(100, 100)
                await page.click(selector, timeout=3000, force=True)
                return True
            except:
                pass
            return False
        
        viewport_x = box['x'] + box['width'] / 2
        viewport_y = box['y'] + box['height'] / 2
        
        if is_mobile:
            print(f"Touching at ({int(viewport_x)}, {int(viewport_y)})")
            await page.touchscreen.tap(viewport_x, viewport_y)
        else:
            screen_x, screen_y = await get_screen_coordinates(page, viewport_x, viewport_y)
            print(f"Moving mouse to ({int(screen_x)}, {int(screen_y)})")
            move_mouse_to_target(screen_x, screen_y)
            click_mouse()
        
        print("Clicked")
        return True
        
    except Exception as e:
        print(f"Click failed: {e}")
        return False

async def close_page_safely(page):
    """Close a page safely - handles URL changes gracefully"""
    try:
        try:
            url = page.url
            print(f"Closing page: {url}")
        except:
            print("Closing page (URL unavailable)")
        
        try:
            await page.evaluate("window.stop()")
        except:
            pass
        
        try:
            await page.close(run_before_unload=False)
            return True
        except:
            pass
        
        try:
            await page.close()
            return True
        except:
            pass
        
        print("Page may already be closed/navigated")
        return True
        
    except Exception as e:
        print(f"Page already gone or changed: {e}")
        return True

async def get_cpmlink_page(context):
    """Get the current cpmlink page - handles URL changes"""
    for page in context.pages:
        try:
            url = page.url
            if url and is_cpmlink_url(url) and "chrome-error" not in url:
                return page
        except:
            continue
    return None

async def get_target_page(context):
    """Get the target page if it exists"""
    for page in context.pages:
        try:
            url = page.url
            if url and is_target_url(url) and "chrome-error" not in url:
                return page
        except:
            continue
    return None

async def cleanup_all_unwanted_tabs(context):
    """Close ALL non-cpmlink, non-target tabs - handles URL changes gracefully"""
    closed_any = False
    pages_to_close = []
    
    for page in context.pages:
        try:
            url = page.url
            
            if should_keep_page(url):
                continue
            
            pages_to_close.append(page)
            
        except:
            pages_to_close.append(page)
    
    for page in pages_to_close:
        try:
            if await close_page_safely(page):
                closed_any = True
        except:
            closed_any = True
    
    return closed_any

async def click_go_to_link_and_handle_popups(context, is_mobile):
    """Click main onclick/Go to Link and handle popups"""
    max_attempts = 15
    
    for attempt in range(1, max_attempts + 1):
        print(f"\n--- Attempt {attempt}/{max_attempts} ---")
        
        await cleanup_all_unwanted_tabs(context)
        
        target_page = await get_target_page(context)
        if target_page:
            print(f"✅ Target URL already open: {target_page.url}")
            return await handle_final_destination(target_page, is_mobile)
        
        cpmlink_page = await get_cpmlink_page(context)
        
        if not cpmlink_page:
            print("No cpmlink page found! Waiting...")
            await asyncio.sleep(1)
            continue
        
        try:
            await cpmlink_page.bring_to_front()
        except:
            cpmlink_page = await get_cpmlink_page(context)
            if not cpmlink_page:
                continue
            await cpmlink_page.bring_to_front()
        
        print(f"On page: {cpmlink_page.url}")
        
        await handle_turnstile(cpmlink_page, is_mobile)
        
        if await check_for_element_simple(cpmlink_page, 'button.confirm', timeout=1000):
            print("Found 'Click to Continue' button")
            old_page = cpmlink_page
            await click_element_at_position(cpmlink_page, 'button.confirm', is_mobile)
            await asyncio.sleep(2)
            print("Closing old page...")
            await close_page_safely(old_page)
            await cleanup_all_unwanted_tabs(context)
            
            cpmlink_page = await get_cpmlink_page(context)
            if cpmlink_page:
                try:
                    await cpmlink_page.bring_to_front()
                except:
                    continue
            else:
                continue
        
        cpmlink_page = await get_cpmlink_page(context)
        if not cpmlink_page:
            continue
        
        try:
            await cpmlink_page.bring_to_front()
        except:
            continue
        
        await handle_turnstile(cpmlink_page, is_mobile)
        
        if await check_for_main_onclick_simple(cpmlink_page):
            print("Found main onclick")
            await check_countdown(cpmlink_page)
            await click_element_at_position(cpmlink_page, 'main#main', is_mobile)
        
        elif await check_for_element_simple(cpmlink_page, 'a.btn.btn-go', timeout=1000):
            print("Found 'Go to Link' button")
            await click_element_at_position(cpmlink_page, 'a.btn.btn-go', is_mobile)
        
        else:
            print("No clickable element found")
            await asyncio.sleep(1)
            continue
        
        await asyncio.sleep(1)
        await cleanup_all_unwanted_tabs(context)
        
        for page in context.pages:
            try:
                url = page.url
                if not url or url == "about:blank":
                    continue
                
                print(f"Page: {url}")
                
                if is_target_url(url):
                    print(f"✅ Found target URL: {url}")
                    return await handle_final_destination(page, is_mobile)
                    
            except:
                continue
    
    return False

async def check_for_element_simple(page, selector, timeout=2000):
    """Check if an element exists"""
    try:
        await page.wait_for_selector(selector, state='attached', timeout=timeout)
        return True
    except:
        return False

async def check_for_main_onclick_simple(page):
    """Check if page has main element with onclick"""
    try:
        return await page.evaluate("""
            () => {
                const main = document.querySelector('main#main');
                return main && main.hasAttribute('onclick');
            }
        """)
    except:
        return False

async def handle_final_destination(page, is_mobile):
    """Handle the final destination page"""
    try:
        url = page.url
        print(f"Final destination: {url}")
        
        await page.bring_to_front()
        
        if "bildirim.online" in url:
            print("Detected bildirim.online")
            wait_time = random.uniform(5, 9)
            print(f"Waiting {wait_time:.1f}s...")
            await asyncio.sleep(wait_time)
            
            print("Clicking 'Allow and Continue'")
            await click_element_at_position(page, 'a#btnPermission', is_mobile)
            await asyncio.sleep(2)
            
            print("Clicking 'Yes'")
            await click_element_at_position(page, 'button#btnYes', is_mobile)
            await asyncio.sleep(3)
            return True
        
        elif "telead.mail.name.ng" in url:
            print("Detected telead.mail.name.ng")
            await asyncio.sleep(3)
            return True
        
        return False
    except:
        return False

async def main():
    if MODE == 1:
        print("MODE 1: Using system defaults (90% mobile, 10% system)")
        if random.random() < 0.9:
            # 90% chance: Use mobile preset
            user_agent = "Mozilla/5.0 (Linux; Android 15; CPH2449) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.1007.19 Mobile Safari/537.36"
            width = 412
            height = 915
            is_mobile = True
            print(f"UA: {user_agent[:80]}...")
            print(f"Viewport: {width}x{height}")
            print(f"Mobile: {is_mobile}")
        else:
            # 10% chance: Use system defaults
            user_agent = None
            width = None
            height = None
            is_mobile = False
            print("Using system defaults")
    else:
        print("MODE 0: Fetching random user agent...")
        user_agent, width, height, is_mobile = await get_random_user_agent()
        print(f"UA: {user_agent[:100]}...")
        print(f"Viewport: {width}x{height}")
        print(f"Mobile: {is_mobile}")
    
    async with async_playwright() as p:
        launch_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-automation',
            '--no-sandbox',
            '--disable-infobars',
            '--disable-dev-shm-usage',
            '--silent-debugger-extension-api',
            '--disable-breakpad',
            '--disable-dev-tools',
            '--disable-hang-monitor',
            '--disable-prompt-on-repost',
            '--disable-sync',
            '--disable-translate',
            '--disable-background-networking',
            '--disable-sync-preferences',
            '--disable-default-apps',
            '--no-first-run',
            '--no-default-browser-check',
        ]
        
        if width and height:
            launch_args.append(f'--window-size={width},{height}')
        launch_args.append('--window-position=0,0')
        
        browser = await p.chromium.launch(
            headless=False,
            proxy={
                "server": "http://127.0.0.1:3000"
            },
            args=launch_args
        )
        
        context_options = {}
        
        if MODE == 0 or (MODE == 1 and user_agent is not None):
            context_options['user_agent'] = user_agent
            context_options['viewport'] = {'width': width, 'height': height}
            context_options['is_mobile'] = is_mobile
            context_options['has_touch'] = is_mobile
        
        context = await browser.new_context(**context_options)
        page = await context.new_page()
        
        print("Navigating to https://cpmlink.co/Rtrs")
        await page.goto("https://cpmlink.co/Rtrs", wait_until='networkidle')
        print("Page loaded")
        
        await page.bring_to_front()
        
        await handle_turnstile(page, is_mobile)
        
        if await check_for_element_simple(page, 'button.confirm', timeout=2000):
            print("Found 'Click to Continue' - clicking...")
            old_page = page
            await click_element_at_position(page, 'button.confirm', is_mobile)
            await asyncio.sleep(2)
            await close_page_safely(old_page)
            await cleanup_all_unwanted_tabs(context)
        
        elif await check_for_main_onclick_simple(page):
            print("Found main onclick - waiting for countdown...")
            await check_countdown(page)
            await click_element_at_position(page, 'main#main', is_mobile)
        
        elif await check_for_element_simple(page, 'a.btn.btn-go', timeout=2000):
            print("Found 'Go to Link' - clicking...")
            await click_element_at_position(page, 'a.btn.btn-go', is_mobile)
        
        success = await click_go_to_link_and_handle_popups(context, is_mobile)
        
        if success:
            print("\n✅ Task completed successfully!")
        else:
            print("\n❌ Task failed")
        
        print("Closing browser in 3 seconds...")
        await asyncio.sleep(3)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
