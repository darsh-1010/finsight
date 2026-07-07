import { RefreshCw, X } from 'lucide-react';
import React from 'react';

import type { BrokerResponse, BrokerCreate } from '@/api/brokers';

type ModalProps = {
  editingBroker: BrokerResponse | null;
  formData: BrokerCreate;
  setFormData: React.Dispatch<React.SetStateAction<BrokerCreate>>;
  closeModal: () => void;
  handleSubmit: (
    e: React.FormEvent,
    editingBroker: BrokerResponse | null,
    formData: BrokerCreate,
  ) => void;
  isSubmitting: boolean;
};

const FormInput = ({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (val: string) => void;
  placeholder: string;
}) => (
  <input
    required
    value={value}
    onChange={(e) => onChange(e.target.value)}
    placeholder={placeholder}
    className="
      w-full px-4 py-2 bg-gray-50
      dark:bg-gray-800 border
      border-gray-200 dark:border-gray-700
      rounded-xl focus:ring-2
      focus:ring-primary/20
    "
  />
);

const FormActions = ({
  isSubmitting,
  editingBroker,
  closeModal,
}: {
  isSubmitting: boolean;
  editingBroker?: BrokerResponse | null;
  closeModal: () => void;
}) => (
  <div className="flex justify-end gap-3 pt-4">
    <button
      type="button"
      onClick={closeModal}
      className="
        px-4 py-2 text-sm font-medium
        text-gray-700 dark:text-gray-300
        hover:bg-gray-100
        dark:hover:bg-gray-800
        rounded-xl
      "
    >
      Cancel
    </button>

    <button
      type="submit"
      disabled={isSubmitting}
      className="
        flex items-center gap-2 px-6 py-2
        bg-primary text-white rounded-xl
        hover:bg-primary/90
        text-sm font-medium
        disabled:opacity-50
      "
    >
      {isSubmitting && <RefreshCw size={14} className="animate-spin" />}
      {editingBroker ? 'Save Changes' : 'Add Broker'}
    </button>
  </div>
);

const BrokerForm = ({
  handleSubmit,
  editingBroker,
  formData,
  setFormData,
  isSubmitting,
  closeModal,
}: ModalProps) => {
  const onSubmit = (e: React.FormEvent) => handleSubmit(e, editingBroker, formData);

  return (
    <form onSubmit={onSubmit} className="p-6 space-y-4">
      <FormInput
        value={formData.name}
        onChange={(val) => setFormData((p) => ({ ...p, name: val }))}
        placeholder="Broker Name"
      />

      <FormInput
        value={formData.redirect_url}
        onChange={(val) => setFormData((p) => ({ ...p, redirect_url: val }))}
        placeholder="https://..."
      />

      <FormActions
        isSubmitting={isSubmitting}
        editingBroker={editingBroker}
        closeModal={closeModal}
      />
    </form>
  );
};

const ModalHeader = ({
  editingBroker,
  closeModal,
}: {
  editingBroker?: BrokerResponse | null;
  closeModal: () => void;
}) => (
  <div
    className="
      flex items-center justify-between
      px-6 py-4 border-b
      border-gray-100 dark:border-gray-800
    "
  >
    <h3 className="text-lg font-bold">
      {editingBroker ? 'Edit Broker' : 'Add Broker'}
    </h3>

    <button
      onClick={closeModal}
      className="
        text-gray-400 hover:text-gray-900
        dark:hover:text-white
      "
    >
      <X size={20} />
    </button>
  </div>
);

const ModalContainer = ({ children }: { children: React.ReactNode }) => (
  <div
    className="
      fixed inset-0 z-50 flex items-center
      justify-center bg-black/50 backdrop-blur-sm
      px-4
    "
  >
    {children}
  </div>
);

const BrokerModal: React.FC<ModalProps> = (props) => (
  <ModalContainer>
    <div
      className="
        bg-white dark:bg-gray-900
        rounded-2xl shadow-xl w-full max-w-md
        border border-gray-200
        dark:border-gray-800 overflow-hidden
      "
    >
      <ModalHeader
        editingBroker={props.editingBroker}
        closeModal={props.closeModal}
      />

      <BrokerForm {...props} />
    </div>
  </ModalContainer>
);

export default BrokerModal;
