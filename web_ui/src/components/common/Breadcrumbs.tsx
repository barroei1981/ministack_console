import { Link } from 'react-router-dom';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface BreadcrumbsProps {
  items: BreadcrumbItem[];
}

export function Breadcrumbs({ items }: BreadcrumbsProps) {
  return (
    <nav className="flex items-center space-x-2 text-sm mb-4">
      {items.map((item, index) => (
        <span key={index} className="flex items-center">
          {index > 0 && (
            <span className="text-gray-400 mx-2">/</span>
          )}
          {item.href ? (
            <Link
              to={item.href}
              className="text-aws-blue hover:text-aws-orange transition-colors"
            >
              {item.label}
            </Link>
          ) : (
            <span className="text-gray-600">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
