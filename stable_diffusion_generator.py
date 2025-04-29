import os
import time
import asyncio
import json
import logging
from typing import Dict, Any, Optional
from fastmcp import FastMCP
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('stable-diffusion-generator')

app = FastMCP()

# Path to store Chrome user data
USER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome-data")
os.makedirs(USER_DATA_DIR, exist_ok=True)

# Global browser instance
browser_instance = None

# Chrome arguments for headless operation
CHROME_ARGS = [
    '--autoplay-policy=user-gesture-required',
    '--disable-background-networking',
    '--disable-background-timer-throttling',
    '--disable-backgrounding-occluded-windows',
    '--disable-breakpad',
    '--disable-client-side-phishing-detection',
    '--disable-component-update',
    '--disable-default-apps',
    '--disable-dev-shm-usage',
    '--disable-domain-reliability',
    '--disable-extensions',
    '--disable-features=AudioServiceOutOfProcess',
    '--disable-hang-monitor',
    '--disable-ipc-flooding-protection',
    '--disable-notifications',
    '--disable-offer-store-unmasked-wallet-cards',
    '--disable-popup-blocking',
    '--disable-print-preview',
    '--disable-prompt-on-repost',
    '--disable-renderer-backgrounding',
    '--disable-setuid-sandbox',
    '--disable-speech-api',
    '--disable-sync',
    '--hide-scrollbars',
    '--ignore-gpu-blacklist',
    '--metrics-recording-only',
    '--mute-audio',
    '--no-default-browser-check',
    '--no-first-run',
    '--no-pings',
    '--no-sandbox',
    '--no-zygote',
    '--password-store=basic',
    '--use-gl=swiftshader',
    '--use-mock-keychain',
]


def setup_browser():
    """Set up and return a Chrome browser instance"""
    global browser_instance
    
    if browser_instance:
        return browser_instance
    
    options = Options()
    options.headless = True
    
    # Add Chrome arguments
    for arg in CHROME_ARGS:
        options.add_argument(arg)
    
    # Set user data directory
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument("--window-size=1280,800")
    
    # Set viewport size
    options.add_experimental_option("mobileEmulation", {"deviceMetrics": {"width": 1280, "height": 800, "pixelRatio": 1.0}})
    
    # Disable cache
    options.add_argument("--disable-application-cache")
    options.add_argument("--disable-cache")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Create browser instance using ChromeDriverManager
    browser_instance = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    browser_instance.set_window_size(1280, 800)
    
    return browser_instance


def cleanup_browser():
    """Clean up the browser instance"""
    global browser_instance
    
    if browser_instance:
        logger.info("Cleaning up browser instance...")
        browser_instance.quit()
        browser_instance = None


def is_logged_in(driver):
    """Check if the user is logged in"""
    try:
        # Quick check by trying to access a protected page
        driver.get("https://stablediffusionweb.com/app/image-generator")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        # Check if redirected to login page
        current_url = driver.current_url
        return not '/auth/login' in current_url
    except Exception as e:
        logger.error(f"Session check failed, will try login: {str(e)}")
        return False


def login(driver):
    """Log in to Stable Diffusion Web"""
    try:
        # Check if already logged in
        if is_logged_in(driver):
            logger.info("Already logged in, proceeding...")
            return True
        
        # Navigate to login page
        logger.info("Navigating to login page...")
        driver.get("https://stablediffusionweb.com/auth/login")
        
        # Wait for page to load completely
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Wait additional time for the page to stabilize
        time.sleep(10)
        
        # Check if we're already on the app page (already logged in)
        if "app" in driver.current_url:
            logger.info("Already logged in (detected from URL)")
            return True
        
        # Look for login form
        try:
            # Wait for email input field with extended timeout
            email_field = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email'], input[placeholder*='email' i]"))
            )
            
            # Wait before interacting
            time.sleep(5)
            
            # Clear and fill email field
            email_field.click()
            time.sleep(1)
            email_field.clear()
            time.sleep(1)
            
            # Get email from environment or use default
            email = os.environ.get("STABLE_DIFFUSION_EMAIL", "")
            if not email:
                logger.warning("No email found in environment variables, using demo account")
                email = "rohanbanda103@gmail.com"  # Replace with your default email
                
            email_field.send_keys(email)
            logger.info("Email entered")
            time.sleep(3)
            
            # Find password field - try multiple selectors
            password_field = None
            for selector in [
                "input[type='password']", 
                "input[name='password']", 
                "input[placeholder*='password' i]"
            ]:
                try:
                    password_field = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
            
            if not password_field:
                raise Exception("Password field not found")
                
            # Clear and fill password field
            password_field.click()
            time.sleep(1)
            password_field.clear()
            time.sleep(1)
            
            # Get password from environment or use default
            password = os.environ.get("STABLE_DIFFUSION_PASSWORD", "")
            if not password:
                logger.warning("No password found in environment variables, using demo account")
                password = "rhn@786105"  # Replace with your default password
                
            password_field.send_keys(password)
            logger.info("Password entered")
            time.sleep(3)
            
            # Find and click login button using multiple methods
            login_clicked = False
            
            # Method 1: Find by common login button selectors
            for selector in [
                "button[type='submit']",
                "input[type='submit']",
                "button:contains('Log in')",
                "button:contains('Sign in')",
                "button:contains('Login')",
                "button:contains('Signin')",
                "a:contains('Log in')",
                "a:contains('Sign in')"
            ]:
                try:
                    login_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    login_button.click()
                    login_clicked = True
                    logger.info(f"Clicked login button using selector: {selector}")
                    break
                except:
                    continue
            
            # Method 2: Use JavaScript if method 1 fails
            if not login_clicked:
                logger.info("Trying JavaScript click for login button")
                login_clicked = driver.execute_script("""
                    // Try to find and click login button
                    function findAndClickLoginButton() {
                        // Method 1: By text content
                        const loginTexts = ['log in', 'sign in', 'login', 'signin'];
                        const buttons = Array.from(document.querySelectorAll('button, input[type="submit"], a.btn, a[role="button"]'));
                        
                        for (const btn of buttons) {
                            const text = btn.textContent.toLowerCase().trim();
                            if (loginTexts.some(loginText => text.includes(loginText))) {
                                btn.click();
                                return true;
                            }
                        }
                        
                        // Method 2: By form submission
                        const form = document.querySelector('form');
                        if (form) {
                            form.submit();
                            return true;
                        }
                        
                        return false;
                    }
                    
                    return findAndClickLoginButton();
                """)
            
            # If still not clicked, try submitting the form directly
            if not login_clicked:
                logger.info("Trying form submission")
                driver.execute_script("""
                    const forms = document.querySelectorAll('form');
                    if (forms.length > 0) {
                        forms[0].submit();
                        return true;
                    }
                    return false;
                """)
            
            # Wait for login to complete
            time.sleep(15)
            
            # Check if login was successful
            if is_logged_in(driver):
                logger.info("Login successful")
                return True
            else:
                # Try one more time with alternative method
                logger.warning("Login may have failed, trying alternative method")
                driver.get("https://stablediffusionweb.com/app/image-generator")
                time.sleep(10)
                
                if is_logged_in(driver):
                    logger.info("Login successful using alternative method")
                    return True
                else:
                    logger.error("Login failed after multiple attempts")
                    driver.save_screenshot('login-failed.png')
                    return False
                
        except Exception as e:
            logger.error(f"Error during login form interaction: {str(e)}")
            driver.save_screenshot('login-error.png')
            return False
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        driver.save_screenshot('login-exception.png')
        return False


@app.tool("generate_image")
async def generate_image(prompt: str) -> Dict[str, Any]:
    """
    Generate an image using Stable Diffusion Web with the given prompt.
    
    This tool logs into stablediffusionweb.com, enters the prompt, and attempts to generate an image.
    It returns the URL of the generated image if successful.
    
    Args:
        prompt: The text prompt to generate an image from
        
    Returns:
        Dictionary containing the status, image URL (if successful), and the original prompt
    """
    global browser_instance
    
    try:
        # Set up browser if not already running
        if not browser_instance:
            browser_instance = setup_browser()
        
        # Ensure login is performed before proceeding
        if not login(browser_instance):
            return {
                "status": "error",
                "message": "Failed to log in to Stable Diffusion Web",
                "imageUrl": None,
                "prompt": prompt
            }
        
        logger.info("Opening Stable Diffusion...")
        browser_instance.get("https://stablediffusionweb.com/app/image-generator")
        WebDriverWait(browser_instance, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # 1. Enter prompt
        prompt_textarea = WebDriverWait(browser_instance, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "textarea#prompts"))
        )
        prompt_textarea.click()
        prompt_textarea.clear()
        prompt_textarea.send_keys(prompt)
        logger.info("Prompt typed")
        
        # 2. Click "Realistic" style - using JavaScript for reliability
        browser_instance.execute_script("""
            // Try to find and click the Realistic style option
            function findAndClickRealisticStyle() {
                // Method 1: By position in style grid (based on the screenshot)
                const styleGrid = document.querySelector('div[role="radiogroup"]');
                if (styleGrid) {
                    const rows = Array.from(styleGrid.children);
                    // Realistic is in the second row, second column (index 1,1)
                    if (rows.length >= 2) {
                        const secondRow = rows[1];
                        const options = Array.from(secondRow.querySelectorAll('div[role="radio"]'));
                        if (options.length >= 2) {
                            options[1].click();
                            return true;
                        }
                    }
                    
                    // Fallback to all options if row structure is different
                    const allOptions = Array.from(styleGrid.querySelectorAll('div[role="radio"]'));
                    // Realistic is often the 5th option (index 4) based on the screenshot
                    if (allOptions.length >= 5) {
                        allOptions[5].click();
                        return true;
                    }
                }
                
                return false;
            }
            
            return findAndClickRealisticStyle();
        """)
        logger.info("Selected 'Realistic' style")
        
        # 3. Scroll down to see image count options
        browser_instance.execute_script("window.scrollBy(0, 500)")
        
        # Set image count = 1 - using JavaScript for reliability
        browser_instance.execute_script("""
            // Try to find and click the "1" option
            function findAndClickOneImage() {
                // Method 1: Find by text content
                const allRadios = Array.from(document.querySelectorAll('div[role="radio"], label, button'));
                for (const radio of allRadios) {
                    if (radio.textContent.trim() === "1") {
                        radio.click();
                        return true;
                    }
                }
                
                // Method 2: Find by position in image count grid (usually the first option)
                const countGrid = document.querySelectorAll('div[role="radiogroup"]');
                if (countGrid.length >= 2) { // Second radiogroup is usually image count
                    const options = Array.from(countGrid[1].querySelectorAll('div[role="radio"]'));
                    if (options.length > 0) {
                        // First option is usually "1"
                        options[0].click();
                        return true;
                    }
                }
                
                return false;
            }
            
            return findAndClickOneImage();
        """)
        logger.info("Image count set to 1")
        
        # 4. Click "Generate" button - using JavaScript for reliability
        clicked = browser_instance.execute_script("""
            // Try to find and click the generate button
            function findAndClickGenerateButton() {
                // Method 1: By text content
                const btns = [...document.querySelectorAll("button")];
                const gen = btns.find(b => b.textContent.trim().toLowerCase() === "generate");
                if (gen) {
                    gen.click();
                    return true;
                }
                
                // Method 2: By common button classes
                const primaryBtns = [...document.querySelectorAll("button[class*='primary'], button[class*='main'], button[class*='generate'], button[type='submit']")];
                if (primaryBtns.length > 0) {
                    primaryBtns[0].click();
                    return true;
                }
                
                // Method 3: Last resort - click any button that might be the generate button
                const allButtons = [...document.querySelectorAll("button:not([class*='cancel']):not([class*='close'])")];
                if (allButtons.length > 0) {
                    allButtons[0].click();
                    return true;
                }
                
                return false;
            }
            
            return findAndClickGenerateButton();
        """)
        
        if not clicked:
            raise Exception("Generate button not found")
            
        logger.info("Clicked Generate")
        
        # Wait for potential error messages
        time.sleep(2)
        
        # Check for "no credits" message
        no_credits = browser_instance.execute_script("""
            // Check for specific no credit messages
            const errorMessages = Array.from(document.querySelectorAll('[role="alert"], [class*="toast"], [class*="notification"], div[class*="error"], div[class*="alert"], span[class*="error"]'));
            
            // Only match exact phrases about no credits
            return errorMessages.some(element => {
                const text = element.textContent?.toLowerCase() || '';
                return text.includes('you have no credits') || 
                       text.includes('no credits available') ||
                       text.includes('no credit available') ||
                       (text.includes('out of credits') && !text.includes('credit is available'));
            });
        """)
        
        if no_credits:
            logger.error("No credits available - detected credit restriction")
            cleanup_browser()
            return {
                "status": "error",
                "message": "No credits available for image generation",
                "imageUrl": None,
                "prompt": prompt
            }
        
        # Get current images before generation
        current_images = browser_instance.execute_script("""
            return Array.from(document.querySelectorAll("img[src*='imgcdn.stablediffusionweb.com']"))
                .map(img => img.src);
        """)
        
        logger.info("Waiting for new image generation...")
        
        # Wait for new image with timeout (5 minutes)
        start_time = time.time()
        timeout = 5 * 60  # 5 minutes
        image_url = None
        
        while time.time() - start_time < timeout:
            # Try to find new images using JavaScript
            new_images = browser_instance.execute_script("""
                const images = Array.from(document.querySelectorAll("img[src*='imgcdn.stablediffusionweb.com']"));
                return images
                    .filter(img => img.complete && img.naturalWidth > 0)
                    .map(img => img.src);
            """)
            
            # Find new images that weren't in the original set
            for img in new_images:
                if img not in current_images and not 'bg-transparent' in img and not 'logo' in img and not 'icon' in img:
                    image_url = img
                    break
            
            if image_url:
                break
                
            # Wait before checking again
            time.sleep(1)
        
        if not image_url:
            logger.error("Image generation timed out")
            cleanup_browser()
            return {
                "status": "error",
                "message": "Image generation timed out after 5 minutes",
                "imageUrl": None,
                "prompt": prompt
            }
        
        logger.info("Image generated")
        logger.info(f"Image URL found: {image_url}")
        
        # Open image in new tab to get final URL
        browser_instance.execute_script(f"window.open('{image_url}', '_blank');")
        
        # Switch to the new tab
        browser_instance.switch_to.window(browser_instance.window_handles[-1])
        
        # Wait for the image to load
        WebDriverWait(browser_instance, 10).until(EC.presence_of_element_located((By.TAG_NAME, "img")))
        
        # Get the final URL
        final_url = browser_instance.current_url
        logger.info(f"Final URL: {final_url}")
        
        # Close the tab and switch back
        browser_instance.close()
        browser_instance.switch_to.window(browser_instance.window_handles[0])
        
        # Clean up browser
        cleanup_browser()
        
        return {
            "status": "success",
            "message": "Image URL retrieved",
            "imageUrl": final_url,
            "prompt": prompt
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        cleanup_browser()
        return {
            "status": "error",
            "message": str(e),
            "imageUrl": None,
            "prompt": prompt
        }


# Register cleanup handlers
import atexit
import signal

atexit.register(cleanup_browser)
signal.signal(signal.SIGTERM, lambda signum, frame: cleanup_browser())
signal.signal(signal.SIGINT, lambda signum, frame: cleanup_browser())

# Run the FastMCP server if executed directly
if __name__ == "__main__":
    app.run()
