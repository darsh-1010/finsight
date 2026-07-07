import { useRef, useState } from 'react';
import type { FormEvent, ChangeEvent } from 'react';

import type { BrokerResponse, BrokerCreate } from '@/api/brokers';
import {
  useGetBrokersQuery,
  useCreateBrokerMutation,
  useUpdateBrokerMutation,
  useDeleteBrokerMutation,
  useUploadBrokersCsvMutation,
} from '@/store/apiSlice';
import { useAlert } from '@/context/AlertContext';

/* ---------------- Modal ---------------- */

const useBrokerModal = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingBroker, setEditingBroker] = useState<BrokerResponse | null>(
    null,
  );

  const [formData, setFormData] = useState({
    name: '',
    redirect_url: '',
  });

  const openCreateModal = () => {
    setEditingBroker(null);
    setFormData({ name: '', redirect_url: '' });
    setIsModalOpen(true);
  };

  const openEditModal = (broker: BrokerResponse) => {
    setEditingBroker(broker);
    setFormData({
      name: broker.name,
      redirect_url: broker.redirect_url,
    });
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingBroker(null);
  };

  return {
    isModalOpen,
    editingBroker,
    formData,
    setFormData,
    openCreateModal,
    openEditModal,
    closeModal,
  };
};

/* ---------------- Main Hook ---------------- */

export const useAdminBrokers = () => {
  const { showAlert } = useAlert();
  const { data: brokers = [], isLoading, error: queryError, refetch } = useGetBrokersQuery();
  const [createBroker, { isLoading: isCreating }] = useCreateBrokerMutation();
  const [updateBroker, { isLoading: isUpdating }] = useUpdateBrokerMutation();
  const [deleteBroker] = useDeleteBrokerMutation();
  const [uploadBrokersCsv, { isLoading: isUploading }] = useUploadBrokersCsvMutation();

  const modal = useBrokerModal();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const error = queryError ? (queryError as any).data?.message || 'Failed to fetch brokers' : null;

  const handleSubmit = async (
    e: FormEvent,
    editingBroker: BrokerResponse | null,
    formData: BrokerCreate,
  ) => {
    e.preventDefault();
    try {
      if (editingBroker) {
        await updateBroker({ id: editingBroker.id, data: formData }).unwrap();
      } else {
        await createBroker(formData).unwrap();
      }
      modal.closeModal();
    } catch (err: unknown) {
      showAlert('Error', err instanceof Error ? err.message : 'Error saving broker');
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this broker?')) return;
    try {
      await deleteBroker(id).unwrap();
    } catch (err: unknown) {
      showAlert('Error', err instanceof Error ? err.message : 'Delete failed');
    }
  };

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.csv')) {
      showAlert('Invalid File', 'Please upload a valid .csv file.');
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    const reader = new FileReader();
    
    reader.onload = async (event) => {
      const text = event.target?.result as string;
      if (!text) {
        showAlert('Error', 'File is empty or cannot be read.');
        if (fileInputRef.current) fileInputRef.current.value = '';
        return;
      }

      const firstLine = text.split('\n')[0]?.toLowerCase().replace(/['"\r]/g, '');
      
      if (!firstLine || !firstLine.includes('name') || !firstLine.includes('redirect_url')) {
        showAlert(
          'Invalid CSV Format',
          'Please ensure your CSV file contains both "name" and "redirect_url" columns.'
        );
        if (fileInputRef.current) fileInputRef.current.value = '';
        return;
      }

      try {
        const res = await uploadBrokersCsv(file).unwrap();
        showAlert('Success', res.message);
        refetch();
      } catch (err: unknown) {
        showAlert('Error', err instanceof Error ? err.message : 'Upload failed');
      } finally {
        if (fileInputRef.current) fileInputRef.current.value = '';
      }
    };

    reader.onerror = () => {
      showAlert('Error', 'Failed to read the file.');
      if (fileInputRef.current) fileInputRef.current.value = '';
    };

    reader.readAsText(file);
  };

  return {
    brokers,
    isLoading,
    error,
    fetchBrokers: refetch,
    ...modal,
    isSubmitting: isCreating || isUpdating,
    handleSubmit,
    handleDelete,
    isUploading,
    fileInputRef,
    handleFileUpload,
  };
};
