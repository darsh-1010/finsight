import { AlertCircle, RefreshCw, Trash2, Edit2 } from 'lucide-react';

import type { BrokerResponse } from '@/api/brokers';

type ContentProps = {
  brokers: BrokerResponse[];
  isLoading: boolean;
  error: string | null;
  fetchBrokers: () => void;
  openEditModal: (b: BrokerResponse) => void;
  handleDelete: (id: number) => void;
};

const LoadingComponent = () => (
  <div
    className="
          flex flex-col items-center justify-center
          py-20 bg-white/50 dark:bg-gray-800/50
          rounded-2xl border border-gray-100
          dark:border-gray-700
        "
  >
    <RefreshCw size={40} className="text-primary animate-spin mb-4" />
    <p className="text-muted-foreground font-medium">Loading brokers...</p>
  </div>
);

const ErrorComponent = ({
  error,
  fetchBrokers,
}: {
  error: string;
  fetchBrokers: () => void;
}) => (
  <div
    className="
          flex flex-col items-center justify-center
          py-20 bg-red-50 dark:bg-red-900/10
          rounded-2xl border border-red-100
          dark:border-red-900/30
        "
  >
    <AlertCircle size={48} className="text-red-500 mb-4" />
    <p className="text-red-700 dark:text-red-300 mb-6">{error}</p>
    <button
      onClick={fetchBrokers}
      className="
            px-6 py-2 bg-red-600 hover:bg-red-700
            text-white rounded-xl font-medium
          "
    >
      Try Again
    </button>
  </div>
);

const TableHeader = () => (
  <thead
    className="
      bg-gray-50/50 dark:bg-gray-800/50
      border-b border-gray-200
      dark:border-gray-800
    "
  >
    <tr>
      <th className="px-6 py-4 text-xs font-semibold">ID</th>
      <th className="px-6 py-4 text-xs font-semibold">Name</th>
      <th className="px-6 py-4 text-xs font-semibold">Redirect URL</th>
      <th className="px-6 py-4 text-right text-xs font-semibold">Actions</th>
    </tr>
  </thead>
);

const TableBody = ({
  brokers,
  handleDelete,
  openEditModal,
}: {
  brokers: BrokerResponse[];
  handleDelete: (id: number) => void;
  openEditModal: (b: BrokerResponse) => void;
}) => (
  <tbody
    className="
      divide-y divide-gray-100
      dark:divide-gray-800
    "
  >
    {brokers.map((broker, i) => (
      <RowComponent
        key={`Broker-component-${i}`}
        broker={broker}
        handleDelete={handleDelete}
        openEditModal={openEditModal}
      />
    ))}
  </tbody>
);

const ActionButtons = ({
  broker,
  handleDelete,
  openEditModal,
}: {
  broker: BrokerResponse;
  handleDelete: (id: number) => void;
  openEditModal: (b: BrokerResponse) => void;
}) => (
  <div className="flex justify-end gap-2">
    <button
      onClick={() => openEditModal(broker)}
      className="
        p-2 text-gray-400
        hover:text-primary
        hover:bg-primary/10
        rounded-lg
      "
    >
      <Edit2 size={16} />
    </button>

    <button
      onClick={() => handleDelete(broker.id)}
      className="
        p-2 text-gray-400
        hover:text-red-500
        hover:bg-red-50
        dark:hover:bg-red-500/10
        rounded-lg
      "
    >
      <Trash2 size={16} />
    </button>
  </div>
);

const RedirectLink = ({ url }: { url: string }) => (
  <a
    href={url}
    target="_blank"
    rel="noopener noreferrer"
    className="text-primary hover:underline"
  >
    {url}
  </a>
);

const RowComponent = ({
  broker,
  handleDelete,
  openEditModal,
}: {
  broker: BrokerResponse;
  handleDelete: (id: number) => void;
  openEditModal: (b: BrokerResponse) => void;
}) => (
  <tr
    className="
      hover:bg-gray-50/50
      dark:hover:bg-gray-800/30
      transition-colors
    "
  >
    <td className="px-6 py-4 text-sm font-medium">{broker.id}</td>

    <td className="px-6 py-4 text-sm font-medium">{broker.name}</td>

    <td className="px-6 py-4 text-sm text-muted-foreground">
      <RedirectLink url={broker.redirect_url} />
    </td>

    <td className="px-6 py-4">
      <ActionButtons
        broker={broker}
        handleDelete={handleDelete}
        openEditModal={openEditModal}
      />
    </td>
  </tr>
);
const TableComponent = ({
  handleDelete,
  brokers,
  openEditModal,
}: {
  brokers: BrokerResponse[];
  handleDelete: (id: number) => void;
  openEditModal: (b: BrokerResponse) => void;
}) => (
  <table className="w-full text-left border-collapse">
    <TableHeader />
    <TableBody
      brokers={brokers}
      handleDelete={handleDelete}
      openEditModal={openEditModal}
    />
  </table>
);

const BrokerContent = ({
  brokers,
  isLoading,
  error,
  fetchBrokers,
  openEditModal,
  handleDelete,
}: ContentProps) => {
  if (isLoading) {
    return <LoadingComponent />;
  }

  if (error) {
    return <ErrorComponent error={error} fetchBrokers={fetchBrokers} />;
  }

  return (
    <div
      className="
        bg-white dark:bg-gray-900/50 backdrop-blur-xl
        rounded-2xl border border-gray-200
        dark:border-gray-800 shadow-sm overflow-hidden
      "
    >
      {brokers.length === 0 ? (
        <div
          className="
            p-12 text-center text-muted-foreground
          "
        >
          No brokers found. Add one manually or upload a CSV.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <TableComponent
            handleDelete={handleDelete}
            brokers={brokers}
            openEditModal={openEditModal}
          />
        </div>
      )}
    </div>
  );
};

export default BrokerContent;
