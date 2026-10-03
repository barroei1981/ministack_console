import { Suspense } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toast } from './components/common/Toast';
import { BucketList } from './components/services/S3/BucketList';
import { BucketDetail } from './components/services/S3/BucketDetail';
import { FunctionList } from './components/services/Lambda/FunctionList';
import { TableList } from './components/services/DynamoDB/TableList';
import { TableCreate } from './components/services/DynamoDB/TableCreate';
import { TableDetail } from './components/services/DynamoDB/TableDetail';

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
          <Routes>
            <Route path="/s3/buckets" element={<BucketList />} />
            <Route path="/s3/buckets/:name" element={<BucketDetail />} />
            <Route path="/lambda/functions" element={<FunctionList />} />
            <Route path="/dynamodb/tables" element={<TableList />} />
            <Route path="/dynamodb/tables/:tableName" element={<TableDetail />} />
            <Route path="/dynamodb/create" element={<TableCreate />} />
          </Routes>
        </BrowserRouter>
        <Toast />
      </QueryClientProvider>
    </Suspense>
  );
}

export default App;
