# MiniStack Console - Web UI

React-based web interface for managing MiniStack resources.

## Setup

### 1. Install Dependencies

```bash
npm install
```

### 2. Environment Variables

Create a `.env` file in this directory (copy from `.env.example`):

```bash
cp .env.example .env
```

Edit `.env` and set:

```
VITE_API_BASE_URL=http://localhost:3001/api
```

The backend API must be running on port 3001 for the frontend to work.

### 3. Start Development Server

```bash
npm run dev
```

The frontend will start on **http://localhost:3000**

### 4. Run Tests

```bash
npm run test
```

## Usage

### S3 Bucket Management

Navigate to: **http://localhost:3000/s3/buckets?tenant_id=YOUR_TENANT_ID**

Replace `YOUR_TENANT_ID` with your 12-digit MiniStack tenant ID.

Features:
- List all S3 buckets for a tenant
- Search/filter buckets by name
- Create new buckets with validation
- View bucket details (versioning, tags, creation date)

## Build for Production

```bash
npm run build
```

The built files will be in the `dist/` directory.

## Project Structure

```
web_ui/
├── src/
│   ├── api/              # API client (Axios)
│   ├── components/       # React components
│   │   ├── common/       # Reusable components (Button, Table, Modal, etc.)
│   │   └── services/     # Service-specific components
│   │       └── S3/       # S3 bucket management
│   ├── hooks/            # React hooks (TanStack Query)
│   ├── i18n/             # Internationalization (i18next)
│   ├── styles/           # CSS (Tailwind + AWS theme)
│   ├── types/            # TypeScript type definitions
│   └── test/             # Test setup
├── package.json
├── vite.config.ts        # Vite configuration
├── tailwind.config.js    # Tailwind CSS configuration
└── tsconfig.json         # TypeScript configuration
```

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **TanStack Query** - Data fetching and caching
- **React Router** - Client-side routing
- **Tailwind CSS** - Styling (AWS Console theme)
- **React Hook Form + Zod** - Form validation
- **Headless UI** - Accessible UI components
- **React Hot Toast** - Toast notifications
- **i18next** - Internationalization
- **Vitest** - Unit testing
- **Testing Library** - Component testing

## Development Notes

### Backend Dependency

The frontend requires the backend API to be running on port 3001. The backend CORS configuration allows requests from `http://localhost:3000`.

### Tenant ID Requirement

All S3 pages require a `tenant_id` query parameter. Without it, a warning message is shown.

### AWS Console Styling

The UI follows AWS Console design patterns:
- **Blue header** (#232f3e)
- **Orange primary buttons** (#ff9900)
- **Gray secondary buttons** and table headers
- Responsive design for laptop screens (1280px+)

### Testing

Tests use Vitest + Testing Library. Run tests with:

```bash
npm run test
```

Coverage report:

```bash
npm run test -- --coverage
```
