import { Suspense } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { Toast } from './components/common/Toast';
import { BucketList } from './components/services/S3/BucketList';
import { BucketDetail } from './components/services/S3/BucketDetail';
import { FunctionList } from './components/services/Lambda/FunctionList';
import { TableList } from './components/services/DynamoDB/TableList';
import { TableCreate } from './components/services/DynamoDB/TableCreate';
import { TableDetail } from './components/services/DynamoDB/TableDetail';
import { UserPoolList } from './components/services/Cognito/UserPoolList';
import { UserPoolDetail } from './components/services/Cognito/UserPoolDetail';
import { IdentityList } from './components/services/SES/IdentityList';
import { QueueList } from './components/services/SQS/QueueList';
import { QueueDetail } from './components/services/SQS/QueueDetail';
import { TopicList } from './components/services/SNS/TopicList';
import { SecretList } from './components/services/Secrets/SecretList';
import { ResourceExplorer } from './components/ResourceExplorer';
import { ResourceGraph } from './components/ResourceGraph';
import { ProjectList } from './components/ProjectList';
import { ProjectDetail } from './components/ProjectDetail';
import { Home } from './components/Home';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      retry: 3,
    },
  },
});

function App() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center min-h-screen">Loading...</div>}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Layout>
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/explorer" element={<ResourceExplorer />} />
              <Route path="/graph" element={<ResourceGraph />} />
              <Route path="/projects" element={<ProjectList />} />
              <Route path="/projects/:projectName" element={<ProjectDetail />} />
              <Route path="/s3/buckets" element={<BucketList />} />
              <Route path="/s3/buckets/:name" element={<BucketDetail />} />
              <Route path="/lambda/functions" element={<FunctionList />} />
              <Route path="/dynamodb/tables" element={<TableList />} />
              <Route path="/dynamodb/tables/:tableName" element={<TableDetail />} />
              <Route path="/dynamodb/create" element={<TableCreate />} />
              <Route path="/cognito/user-pools" element={<UserPoolList />} />
              <Route path="/cognito/user-pools/:poolId" element={<UserPoolDetail />} />
              <Route path="/ses/identities" element={<IdentityList />} />
              <Route path="/sqs/queues" element={<QueueList />} />
              <Route path="/sqs/queues/:queueName" element={<QueueDetail />} />
              <Route path="/lambda/functions" element={<FunctionList />} />
              <Route path="/sns/topics" element={<TopicList />} />
              <Route path="/secrets" element={<SecretList />} />
            </Routes>
          </Layout>
        </BrowserRouter>
        <Toast />
      </QueryClientProvider>
    </Suspense>
  );
}

export default App;
