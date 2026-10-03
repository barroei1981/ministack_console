import { Toaster } from 'react-hot-toast';

export function Toast() {
  return (
    <Toaster
      position="bottom-right"
      toastOptions={{
        duration: 3000,
        style: {
          background: '#363636',
          color: '#fff',
        },
        success: {
          iconTheme: {
            primary: '#ff9900',
            secondary: '#fff',
          },
        },
      }}
    />
  );
}
