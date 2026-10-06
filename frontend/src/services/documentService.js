import api from './api';
import { supabase } from '../lib/supabase';

export const documentService = {
  listDocuments: async () => {
    try {
      const response = await api.get('/api/documents/');
      return response.data;
    } catch (apiErr) {
      console.warn('Backend listDocuments failed, attempting Supabase direct query fallback:', apiErr);
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (user) {
          const { data, error } = await supabase
            .from('clinical_documents')
            .select('*, document_chunks(count)')
            .eq('owner_id', user.id)
            .order('created_at', { ascending: false });

          if (!error && data) {
            return data.map((doc) => {
              const chunkCount = doc.document_chunks?.[0]?.count || 0;
              return {
                ...doc,
                chunk_count: chunkCount,
                rag_indexed: chunkCount > 0,
              };
            });
          }
        }
      } catch (fallbackErr) {
        console.warn('Supabase fallback listDocuments error:', fallbackErr);
      }
      throw apiErr;
    }
  },

  uploadDocument: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/api/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  deleteDocument: async (documentId) => {
    try {
      const response = await api.delete(`/api/documents/${documentId}`);
      return response.data;
    } catch (apiErr) {
      console.warn('Backend deleteDocument failed, attempting Supabase direct delete fallback:', apiErr);
      try {
        const { error } = await supabase
          .from('clinical_documents')
          .delete()
          .eq('id', documentId);
        if (!error) {
          return { status: 'success', message: 'Document deleted' };
        }
      } catch (fallbackErr) {
        console.warn('Supabase fallback delete error:', fallbackErr);
      }
      throw apiErr;
    }
  },

  getDownloadUrl: async (documentId) => {
    try {
      const response = await api.get(`/api/documents/${documentId}/download`);
      return response.data;
    } catch (apiErr) {
      console.warn('Backend getDownloadUrl failed, attempting Supabase direct fallback:', apiErr);
      try {
        const { data: doc, error: fetchErr } = await supabase
          .from('clinical_documents')
          .select('file_path')
          .eq('id', documentId)
          .single();

        if (!fetchErr && doc?.file_path) {
          const { data: signedData, error: signErr } = await supabase.storage
            .from('careflow_documents')
            .createSignedUrl(doc.file_path, 3600);

          if (!signErr && signedData?.signedUrl) {
            return { url: signedData.signedUrl };
          }
        }
      } catch (fallbackErr) {
        console.warn('Supabase fallback getDownloadUrl error:', fallbackErr);
      }
      throw apiErr;
    }
  },
};

