# Screenshots

## TODO: Take Screenshots

To create screenshots for the README:

1. **Start the console:**
   ```bash
   docker-compose up -d
   open http://localhost:3000
   ```

2. **Take these 5 screenshots:**

   **a) Home Page (Dashboard)**
   - Show all service categories
   - Name: `01-home-dashboard.png`

   **b) S3 Management**
   - List of buckets with some data
   - Name: `02-s3-buckets.png`

   **c) DynamoDB Viewer**
   - Table list or table details with items
   - Name: `03-dynamodb-tables.png`

   **d) Lambda Functions**
   - Function list or function detail
   - Name: `04-lambda-functions.png`

   **e) Resource Detail**
   - Any detailed view (S3 bucket detail, DynamoDB table, etc.)
   - Name: `05-resource-detail.png`

3. **Screenshot tips:**
   - Use full browser window (not just content area)
   - Include browser chrome (address bar) to show localhost
   - Use light theme
   - Ensure data is visible (create some test resources if needed)
   - Good resolution: 1920x1080 or higher

4. **Tools:**
   - macOS: Cmd+Shift+4, then Space (window screenshot)
   - Windows: Snipping Tool or Win+Shift+S
   - Linux: Flameshot or GNOME Screenshot

5. **Update README.md:**
   Replace the "TODO" section with:
   ```markdown
   ## Screenshots

   ### Dashboard
   ![Dashboard](./screenshots/01-home-dashboard.png)

   ### S3 Management
   ![S3](./screenshots/02-s3-buckets.png)

   ### DynamoDB Viewer
   ![DynamoDB](./screenshots/03-dynamodb-tables.png)

   ### Lambda Functions
   ![Lambda](./screenshots/04-lambda-functions.png)

   ### Resource Detail
   ![Detail](./screenshots/05-resource-detail.png)
   ```

## Optional: Create Demo GIF

Use a tool like:
- [GIPHY Capture](https://giphy.com/apps/giphycapture) (macOS)
- [ScreenToGif](https://www.screentogif.com/) (Windows)
- [Peek](https://github.com/phw/peek) (Linux)

Show a 30-second workflow:
1. Start console
2. Navigate to S3
3. Create bucket
4. Upload file
5. View file

Save as `demo.gif` in this directory.
