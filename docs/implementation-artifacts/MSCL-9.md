# Story MSCL-9: S3 UI Components (AWS Console Clone)

**Epic:** Epic 2 - S3 Service Management  
**Story Points:** 8  
**Priority:** P0 - Critical Path  
**Dependencies:** MSCL-8 (S3 backend API)

## User Story

As a **developer**,  
I want **AWS Console-style UI for managing S3 buckets**,  
So that **I have a familiar interface for local S3 development**.

## Acceptance Criteria

**Given** I navigate to the S3 service page  
**When** the page loads  
**Then** I see a list of all S3 buckets for the selected tenant  
**And** the layout matches AWS Console style (header, sidebar, content area)  
**And** I see a blue header with "S3" title and search bar  
**And** I see an orange "Create bucket" button in the top-right

**Given** I am viewing the bucket list  
**When** buckets are displayed  
**Then** I see a table with columns: Name, Region, Versioning, Tags, Created Date  
**And** I can sort by any column (ascending/descending)  
**And** I can search/filter buckets by name or tag  
**And** pagination controls appear if >100 buckets

**Given** I click "Create bucket"  
**When** the form modal opens  
**Then** I see a form with: Bucket name (required), Project dropdown, Enable versioning checkbox  
**And** the form validates bucket name (lowercase, no spaces, 3-63 chars)  
**And** invalid names show inline error messages

**Given** I submit the bucket creation form with valid data  
**When** the form is submitted  
**Then** the API is called to create the bucket  
**And** a loading spinner appears during creation  
**And** on success, a toast notification says "Bucket created successfully"  
**And** the new bucket appears in the list immediately (via SSE)

**Given** I click on a bucket name in the list  
**When** the detail page loads  
**Then** I see tabs: Overview, Objects, Properties, Permissions, Tags  
**And** the Overview tab shows: ARN, Region, Versioning status, Object count, Size  
**And** breadcrumbs show: S3 > Buckets > {bucket-name}

**Given** I am on the bucket detail page  
**When** I view the Properties tab  
**Then** I see versioning status with toggle button  
**And** I can enable/disable versioning  
**And** changes are saved immediately with confirmation toast

**Given** I am on the bucket detail page  
**When** I view the Tags tab  
**Then** I see two sections: "Control-Plane Tags" and "Native Tags"  
**And** control-plane tags are editable (add/remove)  
**And** native tags are editable if S3 supports tagging  
**And** tag changes trigger API calls and show success/error messages

**Given** I select a bucket and click "Actions" dropdown  
**When** the dropdown opens  
**Then** I see options: "View details", "Delete bucket", "Empty bucket"  
**And** delete operations require confirmation modal  
**And** confirmation modal warns if bucket has objects

**Given** SSE is connected and a bucket is created elsewhere  
**When** a RESOURCE_CREATED event arrives  
**Then** the bucket list updates automatically without page refresh  
**And** a subtle notification appears (toast or inline message)

## Technical Notes

**Implementation Files:**
- `web_ui/src/components/services/S3/BucketList.tsx` - Bucket list view
- `web_ui/src/components/services/S3/BucketDetail.tsx` - Bucket detail with tabs
- `web_ui/src/components/services/S3/BucketCreate.tsx` - Create bucket modal
- `web_ui/src/hooks/useS3.ts` - React hook for S3 API calls
- `web_ui/src/hooks/useSSE.ts` - SSE real-time updates
- `web_ui/src/store/s3Slice.ts` - S3 state management (Zustand or Redux)

**AWS Console Clone Styling:**
```css
/* AWS-inspired color scheme */
:root {
  --aws-blue: #232f3e;
  --aws-orange: #ff9900;
  --aws-white: #ffffff;
  --aws-gray-light: #f2f3f3;
  --aws-gray-dark: #545b64;
}

.s3-header {
  background: var(--aws-blue);
  color: var(--aws-white);
  padding: 1rem 2rem;
}

.create-button {
  background: var(--aws-orange);
  color: var(--aws-white);
  border: none;
  border-radius: 4px;
  padding: 0.5rem 1rem;
}
```

**Bucket List Component:**
```typescript
// components/services/S3/BucketList.tsx
import { useS3, useSSE } from '../../hooks';
import { Table, Button, SearchBar } from '../../components/common';

export function BucketList() {
  const { buckets, loading, createBucket, deleteBucket } = useS3();
  const [searchQuery, setSearchQuery] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  
  // Real-time updates
  useSSE(currentTenantId);
  
  const filteredBuckets = buckets.filter(b => 
    b.name.toLowerCase().includes(searchQuery.toLowerCase())
  );
  
  return (
    <div className="s3-page">
      <div className="s3-header">
        <h1>S3</h1>
        <SearchBar value={searchQuery} onChange={setSearchQuery} />
        <Button className="create-button" onClick={() => setShowCreateModal(true)}>
          Create bucket
        </Button>
      </div>
      
      <Table
        columns={[
          { key: 'name', label: 'Name', sortable: true },
          { key: 'region', label: 'Region', sortable: true },
          { key: 'versioning', label: 'Versioning', sortable: true },
          { key: 'tags', label: 'Tags', render: (tags) => <TagList tags={tags} /> },
          { key: 'created_at', label: 'Created', sortable: true, render: formatDate }
        ]}
        data={filteredBuckets}
        onRowClick={(bucket) => navigate(`/s3/buckets/${bucket.name}`)}
      />
      
      {showCreateModal && (
        <BucketCreateModal
          onClose={() => setShowCreateModal(false)}
          onSubmit={createBucket}
        />
      )}
    </div>
  );
}
```

**Bucket Detail Component:**
```typescript
// components/services/S3/BucketDetail.tsx
import { Tabs, TagList } from '../../components/common';

export function BucketDetail({ bucketName }) {
  const { bucket, loading } = useS3Bucket(bucketName);
  
  return (
    <div className="bucket-detail">
      <Breadcrumbs>
        <BreadcrumbItem to="/s3">S3</BreadcrumbItem>
        <BreadcrumbItem to="/s3/buckets">Buckets</BreadcrumbItem>
        <BreadcrumbItem>{bucketName}</BreadcrumbItem>
      </Breadcrumbs>
      
      <h1>{bucketName}</h1>
      
      <Tabs>
        <Tab label="Overview">
          <dl>
            <dt>ARN</dt><dd><code>{bucket.arn}</code></dd>
            <dt>Region</dt><dd>{bucket.state.region}</dd>
            <dt>Versioning</dt><dd>{bucket.state.versioning}</dd>
          </dl>
        </Tab>
        
        <Tab label="Objects">
          <ObjectBrowser bucketName={bucketName} />
        </Tab>
        
        <Tab label="Properties">
          <VersioningToggle bucket={bucket} />
        </Tab>
        
        <Tab label="Tags">
          <TagSection title="Control-Plane Tags" tags={bucket.tags.control_plane} editable />
          <TagSection title="Native Tags" tags={bucket.tags.native} editable />
        </Tab>
      </Tabs>
    </div>
  );
}
```

**Testing:**
- Unit tests: Component rendering, user interactions, form validation
- Integration tests: API calls from UI, SSE event handling
- E2E tests (Playwright): Full user flow: create bucket → view details → delete bucket
- Visual regression tests: AWS Console style matching

**NFRs Addressed:**
- NFR-5 (Usability): AWS Console-style interface, familiar navigation
- NFR-1 (Performance): UI loads <2s, list loads <500ms
- FR-5: S3 Service Dashboard (UI portion)

**Architecture Decisions:**
- AD-7: AWS Console Clone UI Paradigm
- AD-14: Hybrid LocalStorage for UI State Persistence (search filters, table sorting)
