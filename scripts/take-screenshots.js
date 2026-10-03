/**
 * Automated screenshot capture for MiniStack Console
 * Run with: node scripts/take-screenshots.js
 */

const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const CONSOLE_URL = 'http://localhost:3000';
const SCREENSHOTS_DIR = path.join(__dirname, '..', 'screenshots');
const TENANT_ID = '000000000001';

// Ensure screenshots directory exists
if (!fs.existsSync(SCREENSHOTS_DIR)) {
  fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

async function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function takeScreenshot(page, name, fullPage = false) {
  const filename = path.join(SCREENSHOTS_DIR, `${name}.png`);
  await page.screenshot({
    path: filename,
    fullPage,
    animations: 'disabled'
  });
  console.log(`✅ Captured: ${name}.png`);
}

async function setupTestData(page) {
  console.log('🔧 Setting up test data...');

  // Just navigate to ensure pages load
  try {
    await page.goto(`${CONSOLE_URL}/s3/buckets?tenant_id=${TENANT_ID}`);
    await delay(2000);
  } catch (error) {
    console.log('⚠️  Could not load S3:', error.message);
  }

  try {
    await page.goto(`${CONSOLE_URL}/dynamodb/tables?tenant_id=${TENANT_ID}`);
    await delay(2000);
  } catch (error) {
    console.log('⚠️  Could not load DynamoDB:', error.message);
  }

  console.log('✅ Test data setup complete');
}

async function captureScreenshots() {
  console.log('🚀 Starting screenshot capture...\n');

  const browser = await chromium.launch({
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 2, // Retina/high-DPI
  });

  const page = await context.newPage();

  try {
    // Wait for console to be ready
    console.log('⏳ Waiting for console to be ready...');
    await page.goto(CONSOLE_URL, { waitUntil: 'networkidle', timeout: 30000 });
    await delay(3000);

    // Setup test data first
    await setupTestData(page);

    // 1. Home Page (Dashboard)
    console.log('\n📸 Capturing: Home Dashboard');
    await page.goto(`${CONSOLE_URL}/?tenant_id=${TENANT_ID}`, { waitUntil: 'networkidle', timeout: 30000 });
    await delay(2000);
    await takeScreenshot(page, '01-home-dashboard', true);

    // 2. S3 Management
    console.log('\n📸 Capturing: S3 Buckets');
    await page.goto(`${CONSOLE_URL}/s3/buckets?tenant_id=${TENANT_ID}`, { waitUntil: 'networkidle', timeout: 30000 });
    await delay(2000);
    await takeScreenshot(page, '02-s3-buckets', true);

    // 3. DynamoDB Tables
    console.log('\n📸 Capturing: DynamoDB Tables');
    await page.goto(`${CONSOLE_URL}/dynamodb/tables?tenant_id=${TENANT_ID}`, { waitUntil: 'networkidle', timeout: 30000 });
    await delay(2000);
    await takeScreenshot(page, '03-dynamodb-tables', true);

    // 4. Lambda Functions
    console.log('\n📸 Capturing: Lambda Functions');
    await page.goto(`${CONSOLE_URL}/lambda/functions?tenant_id=${TENANT_ID}`, { waitUntil: 'networkidle', timeout: 30000 });
    await delay(2000);
    await takeScreenshot(page, '04-lambda-functions', true);

    // 5. SQS Queues
    console.log('\n📸 Capturing: SQS Queues');
    await page.goto(`${CONSOLE_URL}/sqs/queues?tenant_id=${TENANT_ID}`, { waitUntil: 'networkidle', timeout: 30000 });
    await delay(2000);
    await takeScreenshot(page, '05-sqs-queues', true);

    // 6. Cognito User Pools
    console.log('\n📸 Capturing: Cognito User Pools');
    await page.goto(`${CONSOLE_URL}/cognito/user-pools?tenant_id=${TENANT_ID}`, { waitUntil: 'networkidle', timeout: 30000 });
    await delay(2000);
    await takeScreenshot(page, '06-cognito-pools', true);

    console.log('\n✅ All screenshots captured successfully!\n');
    console.log(`📁 Screenshots saved to: ${SCREENSHOTS_DIR}\n`);

  } catch (error) {
    console.error('❌ Error capturing screenshots:', error.message);
    throw error;
  } finally {
    await browser.close();
  }
}

// Main execution
(async () => {
  try {
    // Check if console is running
    const response = await fetch(CONSOLE_URL).catch(() => null);
    if (!response) {
      console.error('❌ Console not running!');
      console.log('\nPlease start the console first:');
      console.log('  docker-compose up -d');
      console.log('  open http://localhost:3000');
      console.log('\nThen run this script again.\n');
      process.exit(1);
    }

    await captureScreenshots();

    console.log('🎉 Screenshot capture complete!');
    console.log('\nNext steps:');
    console.log('1. Review screenshots in /screenshots/ directory');
    console.log('2. Run: npm run update-readme');
    console.log('3. Commit and push to GitHub\n');

  } catch (error) {
    console.error('❌ Failed:', error.message);
    process.exit(1);
  }
})();
