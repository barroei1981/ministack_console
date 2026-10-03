import { Link, useSearchParams } from 'react-router-dom';

interface Service {
  name: string;
  fullName: string;
  path: string;
  description: string;
}

interface ServiceCategory {
  title: string;
  description: string;
  services: Service[];
}

export function Home() {
  const [searchParams] = useSearchParams();
  const tenantId = searchParams.get('tenant_id') || '000000000001';

  const categories: ServiceCategory[] = [
    {
      title: 'Storage',
      description: 'Store and retrieve any amount of data from anywhere',
      services: [
        {
          name: 'S3',
          fullName: 'Simple Storage Service',
          path: `/s3/buckets?tenant_id=${tenantId}`,
          description: 'Scalable object storage for any type of data',
        },
      ],
    },
    {
      title: 'Database',
      description: 'Managed database services for all your application needs',
      services: [
        {
          name: 'DynamoDB',
          fullName: 'DynamoDB',
          path: `/dynamodb/tables?tenant_id=${tenantId}`,
          description: 'Fast and flexible NoSQL database service',
        },
        {
          name: 'RDS',
          fullName: 'Relational Database Service',
          path: `/rds/instances?tenant_id=${tenantId}`,
          description: 'Managed relational databases (PostgreSQL, MySQL)',
        },
      ],
    },
    {
      title: 'Compute',
      description: 'Secure and resizable compute capacity in the cloud',
      services: [
        {
          name: 'Lambda',
          fullName: 'Lambda',
          path: `/lambda/functions?tenant_id=${tenantId}`,
          description: 'Run code without thinking about servers',
        },
      ],
    },
    {
      title: 'Application Integration',
      description: 'Connect distributed applications and services',
      services: [
        {
          name: 'SES',
          fullName: 'Simple Email Service',
          path: `/ses/identities?tenant_id=${tenantId}`,
          description: 'Reliable, scalable email sending service',
        },
        {
          name: 'SQS',
          fullName: 'Simple Queue Service',
          path: `/sqs/queues?tenant_id=${tenantId}`,
          description: 'Managed message queuing service',
        },
        {
          name: 'SNS',
          fullName: 'Simple Notification Service',
          path: `/sns/topics?tenant_id=${tenantId}`,
          description: 'Pub/sub messaging and mobile notifications',
        },
      ],
    },
    {
      title: 'Security, Identity & Compliance',
      description: 'Protect your data and meet compliance requirements',
      services: [
        {
          name: 'IAM',
          fullName: 'Identity and Access Management',
          path: `/iam/users?tenant_id=${tenantId}`,
          description: 'Securely manage access to services and resources',
        },
        {
          name: 'Cognito',
          fullName: 'Cognito',
          path: `/cognito/user-pools?tenant_id=${tenantId}`,
          description: 'User identity and access for your applications',
        },
        {
          name: 'Secrets Manager',
          fullName: 'Secrets Manager',
          path: `/secretsmanager/secrets?tenant_id=${tenantId}`,
          description: 'Rotate, manage, and retrieve secrets',
        },
      ],
    },
    {
      title: 'Management & Governance',
      description: 'Manage and monitor your cloud resources',
      services: [
        {
          name: 'CloudWatch',
          fullName: 'CloudWatch',
          path: `/cloudwatch/logs?tenant_id=${tenantId}`,
          description: 'Monitor resources and applications',
        },
      ],
    },
    {
      title: 'Developer Tools',
      description: 'Tools to build, deploy, and maintain cloud applications',
      services: [
        {
          name: 'Resource Explorer',
          fullName: 'Resource Explorer',
          path: `/explorer?tenant_id=${tenantId}`,
          description: 'Search and discover resources across all services',
        },
        {
          name: 'Resource Graph',
          fullName: 'Resource Relationship Graph',
          path: `/graph?tenant_id=${tenantId}`,
          description: 'Visualize dependencies between resources',
        },
        {
          name: 'Projects',
          fullName: 'Project Management',
          path: `/projects?tenant_id=${tenantId}`,
          description: 'Group and organize resources by project',
        },
      ],
    },
  ];

  return (
    <div className="bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Breadcrumb */}
        <nav className="text-sm mb-4">
          <span className="text-gray-500">Console Home</span>
        </nav>

        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-normal text-gray-900">AWS services</h1>
        </div>

        {/* Service Categories */}
        <div className="space-y-10">
          {categories.map((category) => (
            <div key={category.title} className="border-b border-gray-200 pb-10 last:border-b-0">
              <div className="mb-4">
                <h2 className="text-lg font-semibold text-gray-900">{category.title}</h2>
                <p className="text-sm text-gray-600 mt-1">{category.description}</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {category.services.map((service) => (
                  <Link
                    key={service.name}
                    to={service.path}
                    className="block p-4 border border-gray-200 rounded hover:border-orange-500 hover:shadow-md transition-all bg-white"
                  >
                    <div className="flex items-start">
                      <div className="flex-1">
                        <h3 className="text-sm font-semibold text-blue-600 hover:text-orange-600">
                          {service.name}
                        </h3>
                        <p className="text-xs text-gray-500 mt-0.5">{service.fullName}</p>
                        <p className="text-sm text-gray-700 mt-2 leading-relaxed">
                          {service.description}
                        </p>
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Info Banner - AWS Console Style */}
        <div className="mt-10 bg-blue-50 border-l-4 border-blue-400 p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-blue-800">MiniStack Console</h3>
              <div className="mt-2 text-sm text-blue-700">
                <p>
                  You are using the MiniStack Console, a local AWS emulator running on{' '}
                  <code className="bg-blue-100 px-1.5 py-0.5 rounded font-mono text-xs">localhost:4566</code>
                </p>
                <p className="mt-2">
                  Switch tenants using the dropdown in the top navigation bar. Each tenant provides isolated resources.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
