import React from 'react';

import BrokerContent from '@/components/admin/broker/BrokerContent';
import BrokerHeader from '@/components/admin/broker/BrokerHeader';
import BrokerModal from '@/components/admin/broker/BrokerModal';
import { useAdminBrokers } from '@/hooks/useAdminBrokers';

type ViewProps = ReturnType<typeof useAdminBrokers>;

const AdminBrokersView: React.FC<ViewProps> = (state) => (
  <div
    className="
        max-w-7xl mx-auto p-6 md:p-8 space-y-8
      "
  >
    <BrokerHeader
      isUploading={state.isUploading}
      fileInputRef={state.fileInputRef}
      handleFileUpload={state.handleFileUpload}
      openCreateModal={state.openCreateModal}
    />

    <BrokerContent
      brokers={state.brokers}
      isLoading={state.isLoading}
      error={state.error}
      fetchBrokers={state.fetchBrokers}
      openEditModal={state.openEditModal}
      handleDelete={state.handleDelete}
    />

    {state.isModalOpen && (
      <BrokerModal
        editingBroker={state.editingBroker}
        formData={state.formData}
        setFormData={state.setFormData}
        closeModal={state.closeModal}
        handleSubmit={state.handleSubmit}
        isSubmitting={state.isSubmitting}
      />
    )}
  </div>
);

const AdminBrokersPage: React.FC = () => {
  const state = useAdminBrokers();

  return <AdminBrokersView {...state} />;
};

export default AdminBrokersPage;
