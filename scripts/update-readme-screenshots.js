/**
 * Update README.md with screenshot links
 * Run with: node scripts/update-readme-screenshots.js
 */

const fs = require('fs');
const path = require('path');

const README_PATH = path.join(__dirname, '..', 'README.md');
const SCREENSHOTS_DIR = path.join(__dirname, '..', 'screenshots');

// Read README
let readme = fs.readFileSync(README_PATH, 'utf-8');

// Screenshot section to replace
const screenshotSection = `## Screenshots

### Dashboard
![Dashboard](./screenshots/01-home-dashboard.png)
*Service categories and navigation*

### S3 Management
![S3 Buckets](./screenshots/02-s3-buckets.png)
*S3 bucket management interface*

### DynamoDB Viewer
![DynamoDB Tables](./screenshots/03-dynamodb-tables.png)
*DynamoDB table viewer with optimized performance*

### Lambda Functions
![Lambda](./screenshots/04-lambda-functions.png)
*Lambda function management*

### Resource Detail View
![Detail View](./screenshots/05-resource-detail.png)
*Detailed resource management interface*`;

// Find and replace screenshot section
const screenshotStart = readme.indexOf('## Screenshots');
const screenshotEnd = readme.indexOf('## Features', screenshotStart);

if (screenshotStart !== -1 && screenshotEnd !== -1) {
  const before = readme.substring(0, screenshotStart);
  const after = readme.substring(screenshotEnd);

  readme = before + screenshotSection + '\n\n' + after;

  fs.writeFileSync(README_PATH, readme);
  console.log('✅ README.md updated with screenshot links!');
  console.log('\nScreenshots added:');
  console.log('  - 01-home-dashboard.png');
  console.log('  - 02-s3-buckets.png');
  console.log('  - 03-dynamodb-tables.png');
  console.log('  - 04-lambda-functions.png');
  console.log('  - 05-resource-detail.png');
  console.log('\nNext: Commit and push to GitHub\n');
} else {
  console.error('❌ Could not find Screenshots section in README.md');
  process.exit(1);
}
