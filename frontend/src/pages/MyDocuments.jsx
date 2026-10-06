import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { documentService } from '../services/documentService';
import { UploadCloud, File, Trash2, Download, CheckCircle, AlertCircle, RefreshCw, Sparkles, FolderOpen } from 'lucide-react';

export const MyDocuments = () => {
  const { user } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState({ type: '', message: '' });
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await documentService.listDocuments();
      if (Array.isArray(data)) {
        setDocuments(data);
      }
    } catch (err) {
      console.error('Error fetching documents:', err);
      const detail = err.response?.data?.detail || err.message || 'Failed to load documents.';
      setError(typeof detail === 'string' ? detail : 'Failed to load documents.');
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = async (e) => {
    if (uploading) return;
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate size (10MB max)
    if (file.size > 10 * 1024 * 1024) {
      setUploadStatus({ type: 'error', message: 'File size exceeds 10MB limit.' });
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    // Validate type
    const allowedTypes = ['application/pdf', 'text/plain', 'text/markdown', 'image/jpeg', 'image/png'];
    const ext = file.name.split('.').pop().toLowerCase();
    const isAllowedExt = ['pdf', 'txt', 'md', 'jpg', 'jpeg', 'png'].includes(ext);
    
    if (!allowedTypes.includes(file.type) && !isAllowedExt) {
      setUploadStatus({ type: 'error', message: 'Unsupported file format. Please upload PDF, TXT, MD, JPG, or PNG.' });
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    try {
      setUploading(true);
      setUploadStatus({ type: 'info', message: 'Uploading document...' });
      
      // Simulate progress for UX
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => (prev >= 90 ? 90 : prev + 10));
      }, 300);

      const newDoc = await documentService.uploadDocument(file);
      
      clearInterval(progressInterval);
      setUploadProgress(100);
      
      const ragIndexed = newDoc.rag_indexed ?? ((newDoc.chunk_count || 0) > 0);
      const successMsg = ragIndexed
        ? `Document uploaded and indexed (${newDoc.chunk_count || 0} chunks ready for RAG)!`
        : 'Document uploaded successfully!';
      setUploadStatus({ type: 'success', message: successMsg });
      
      // Add newly uploaded document immediately to the state
      setDocuments(prev => [newDoc, ...prev.filter(d => d.id !== newDoc.id)]);
      
      // Refresh list in background to sync state without breaking UI if background fetch fails
      try {
        const refreshedData = await documentService.listDocuments();
        if (Array.isArray(refreshedData)) {
          setDocuments(refreshedData);
        }
      } catch (refreshErr) {
        console.warn('Background list refresh warning (upload still succeeded):', refreshErr);
      }
    } catch (err) {
      console.error('Upload error:', err);
      let errMsg = 'Failed to upload document. Please try again.';
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        errMsg = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        errMsg = detail.map(d => d.msg || (typeof d === 'string' ? d : JSON.stringify(d))).join(', ');
      } else if (detail && typeof detail === 'object') {
        errMsg = detail.message || JSON.stringify(detail);
      } else if (err.message) {
        errMsg = err.message;
      }
      setUploadStatus({ 
        type: 'error', 
        message: errMsg 
      });
    } finally {
      setUploading(false);
      setTimeout(() => {
        setUploadProgress(0);
      }, 1000);
      setTimeout(() => {
        setUploadStatus({ type: '', message: '' });
      }, 6000);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (docId) => {
    if (!window.confirm('Are you sure you want to delete this document?')) return;
    
    try {
      await documentService.deleteDocument(docId);
      setDocuments(prev => prev.filter(doc => doc.id !== docId));
    } catch (err) {
      console.error('Delete error:', err);
      alert('Failed to delete document.');
    }
  };

  const handleDownload = async (docId) => {
    try {
      const { url } = await documentService.getDownloadUrl(docId);
      if (url) {
        window.open(url, '_blank');
      } else {
        alert('Could not obtain download URL.');
      }
    } catch (err) {
      console.error('Download error:', err);
      alert('Failed to generate download link.');
    }
  };

  const renderRagStatus = (doc) => {
    const isImage = doc.file_type?.startsWith('image/') || /\.(jpg|jpeg|png)$/i.test(doc.title || '');
    if (isImage) {
      return (
        <span className="bg-slate-800 text-slate-400 border border-white/[0.06] px-2.5 py-0.5 rounded-full text-[10px] font-medium">
          Attachment (No RAG)
        </span>
      );
    }

    const chunkCount = doc.chunk_count || 0;
    const isIndexed = doc.rag_indexed || chunkCount > 0;

    if (isIndexed) {
      return (
        <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2.5 py-0.5 rounded-full text-[10px] font-medium inline-flex items-center gap-1">
          <Sparkles className="w-3 h-3 inline" />
          Searchable (RAG){chunkCount > 0 ? ` • ${chunkCount} chunk${chunkCount === 1 ? '' : 's'}` : ''}
        </span>
      );
    }

    return (
      <span className="bg-amber-500/10 text-amber-300 border border-amber-500/20 px-2.5 py-0.5 rounded-full text-[10px] font-medium">
        No text extracted
      </span>
    );
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-[#6355d8] via-[#735df2] to-[#8c75ff] p-8 text-white shadow-xl shadow-purple-900/20">
        <div className="absolute top-0 right-0 w-80 h-80 bg-white/10 rounded-full blur-2xl pointer-events-none -mr-20 -mt-20" />
        <div className="relative z-10 space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-white/20 text-white backdrop-blur-md">
            <FolderOpen className="w-3.5 h-3.5" /> Medical Documents &amp; Vector Store
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            My Documents &amp; Clinical Knowledge
          </h1>
          <p className="text-xs sm:text-sm text-purple-100/90 max-w-2xl">
            Securely upload and manage your clinical records and reference literature. Files are automatically processed for grounded AI search.
          </p>
        </div>
      </div>

      {/* Upload Section */}
      <div className="bg-[#181926] rounded-3xl border border-white/[0.08] p-6 sm:p-8 shadow-xl">
        <div className="flex flex-col items-center justify-center w-full">
          <label 
            htmlFor="dropzone-file" 
            className={`flex flex-col items-center justify-center w-full h-44 border-2 border-dashed rounded-2xl cursor-pointer transition-all ${
              uploading
                ? 'bg-purple-900/10 border-purple-500/40 cursor-not-allowed opacity-75'
                : 'bg-[#12131d] border-white/[0.1] hover:border-purple-500/50 hover:bg-[#151622]'
            }`}
          >
            <div className="flex flex-col items-center justify-center pt-5 pb-6">
              <UploadCloud className={`w-10 h-10 mb-3 ${uploading ? 'text-purple-400 animate-bounce' : 'text-purple-400/80'}`} />
              <p className="mb-1 text-sm text-slate-200">
                <span className="font-bold text-white">{uploading ? 'Uploading and indexing vector embeddings...' : 'Click to upload'}</span> {!uploading && 'or drag and drop'}
              </p>
              <p className="text-xs text-slate-400">
                PDF, TXT, MD, JPG, PNG (Max 10MB)
              </p>
            </div>
            <input 
              ref={fileInputRef}
              id="dropzone-file" 
              type="file" 
              className="hidden" 
              onChange={handleFileChange}
              disabled={uploading}
              accept=".pdf,.txt,.md,.jpg,.jpeg,.png,application/pdf,text/plain,text/markdown,image/jpeg,image/png"
            />
          </label>
        </div>

        {uploading && (
          <div className="mt-4 w-full bg-[#12131d] rounded-full h-2.5 overflow-hidden border border-white/[0.05]">
            <div 
              className="bg-gradient-to-r from-purple-500 to-indigo-500 h-2.5 rounded-full transition-all duration-300 shadow-md shadow-purple-500/50" 
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        )}

        {uploadStatus.message && (
          <div className={`mt-4 p-3.5 rounded-2xl flex items-center gap-2.5 text-xs font-medium ${
            uploadStatus.type === 'error'
              ? 'bg-rose-500/10 border border-rose-500/20 text-rose-300'
              : uploadStatus.type === 'success'
              ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-300'
              : 'bg-purple-500/10 border border-purple-500/20 text-purple-300'
          }`}>
            {uploadStatus.type === 'error' ? (
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            ) : (
              <CheckCircle className="w-4 h-4 shrink-0 text-emerald-400" />
            )}
            <span>{uploadStatus.message}</span>
          </div>
        )}
      </div>

      {/* Documents List */}
      <div className="bg-[#181926] rounded-3xl border border-white/[0.08] shadow-xl overflow-hidden">
        <div className="px-6 py-5 border-b border-white/[0.06] flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-white">Uploaded Documents ({documents.length})</h3>
            <p className="text-xs text-slate-400 mt-0.5">Clinical references available for RAG grounding</p>
          </div>
          <button
            onClick={fetchDocuments}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:text-white bg-[#12131d] hover:bg-white/[0.05] border border-white/[0.08] rounded-xl transition-colors cursor-pointer"
            title="Refresh document list"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
        
        {loading && documents.length === 0 ? (
          <div className="p-16 text-center text-slate-400">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500 mx-auto mb-4" />
            Loading clinical documents...
          </div>
        ) : error && documents.length === 0 ? (
          <div className="p-12 text-center space-y-3">
            <AlertCircle className="w-10 h-10 text-rose-400 mx-auto" />
            <p className="text-rose-400 font-medium text-xs">{error}</p>
            <button
              onClick={fetchDocuments}
              className="inline-flex items-center gap-2 px-4 py-2 bg-[#6c5dd3] hover:bg-purple-600 text-white text-xs font-bold rounded-xl transition-colors shadow-md shadow-purple-600/20 cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Try Again
            </button>
          </div>
        ) : documents.length === 0 ? (
          <div className="p-16 text-center text-slate-400 flex flex-col items-center space-y-3">
            <File className="w-12 h-12 text-slate-500" />
            <p className="font-bold text-slate-300 text-sm">No documents uploaded yet</p>
            <p className="text-xs text-slate-400 max-w-sm">
              Upload clinical guidelines, medical records, or consultation notes to search and reference them with CareFlow AI.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-white/[0.06]">
            {documents.map((doc) => (
              <li key={doc.id} className="p-5 hover:bg-white/[0.02] transition-colors flex items-center justify-between group">
                <div className="flex items-start gap-4 min-w-0">
                  <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-purple-500/20 to-indigo-500/20 border border-purple-500/30 flex items-center justify-center text-purple-400 shrink-0">
                    <File className="w-5 h-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-bold text-slate-100 truncate">
                      {doc.title}
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
                      <span className="font-mono">{doc.file_type || 'Unknown type'}</span>
                      {doc.file_size && <span>&bull; {(doc.file_size / 1024 / 1024).toFixed(2)} MB</span>}
                      <span>
                        &bull; {doc.created_at ? new Date(doc.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'Recently'}
                      </span>
                      {renderRagStatus(doc)}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0 opacity-80 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => handleDownload(doc.id)}
                    className="p-2 text-slate-400 hover:text-purple-300 bg-[#12131d] hover:bg-white/[0.06] border border-white/[0.08] rounded-xl transition-colors cursor-pointer"
                    title="Download"
                  >
                    <Download className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    className="p-2 text-slate-400 hover:text-rose-400 bg-[#12131d] hover:bg-rose-500/10 border border-white/[0.08] rounded-xl transition-colors cursor-pointer"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
