'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { getUsers, updateRole, getDocuments, getStats } from '@/lib/api';
import type { User, DocumentInfo, StatsResponse } from '@/lib/types';
import { COLLECTION_COLORS } from '@/lib/types';

const ALL_ROLES = ['employee', 'finance_analyst', 'engineer', 'marketing_specialist', 'executive', 'hr_representative'];

export default function AdminPage() {
  const router = useRouter();
  const { isAuthenticated, isExecutive } = useAuth();
  const [tab, setTab] = useState<'users' | 'documents' | 'stats'>('users');
  const [users, setUsers] = useState<User[]>([]);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) { router.replace('/login'); return; }
    if (!isExecutive) { router.replace('/chat'); return; }
    loadData();
  }, [isAuthenticated, isExecutive, router]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [u, d, s] = await Promise.all([getUsers(), getDocuments(), getStats()]);
      setUsers(u);
      setDocuments(d);
      setStats(s);
    } catch (err) {
      console.error('Failed to load admin data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleRoleChange = async (userId: string, newRole: string) => {
    try {
      await updateRole(userId, newRole);
      setUsers(prev => prev.map(u => (u.id === userId ? { ...u, role: newRole } : u)));
    } catch (err: any) {
      alert(err.message);
    }
  };

  if (loading) {
    return (
      <div className="admin-page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <div className="typing-indicator">
          <div className="typing-dot" />
          <div className="typing-dot" />
          <div className="typing-dot" />
        </div>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <header className="admin-header">
        <h1 style={{ fontSize: 18, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
          ⚙️ Admin Panel
        </h1>
        <button className="btn btn-ghost" onClick={() => router.push('/chat')} style={{ fontSize: 13 }}>
          ← Back to Chat
        </button>
      </header>

      <div className="admin-content animate-fade-in">
        {/* Tabs */}
        <div className="admin-tabs">
          {(['users', 'documents', 'stats'] as const).map(t => (
            <button key={t} className={`admin-tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
              {t === 'users' ? '👥 Users' : t === 'documents' ? '📄 Documents' : '📊 Stats'}
            </button>
          ))}
        </div>

        {/* Users Tab */}
        {tab === 'users' && (
          <table className="data-table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Current Role</th>
                <th>Change Role</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id}>
                  <td style={{ fontWeight: 500 }}>{u.username}</td>
                  <td>
                    <span className="badge badge-role">{u.role.replace(/_/g, ' ')}</span>
                  </td>
                  <td>
                    <select
                      value={u.role}
                      onChange={e => handleRoleChange(u.id, e.target.value)}
                      className="input"
                      style={{ width: 'auto', padding: '6px 12px', fontSize: 13 }}
                    >
                      {ALL_ROLES.map(r => (
                        <option key={r} value={r}>{r.replace(/_/g, ' ')}</option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Documents Tab */}
        {tab === 'documents' && (
          <>
            {documents.length === 0 ? (
              <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 40 }}>
                No documents ingested yet. Run the ingestion CLI first.
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Filename</th>
                    <th>Collection</th>
                    <th>Chunks</th>
                    <th>Access Roles</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 500 }}>📄 {doc.filename}</td>
                      <td>
                        <span className={`badge badge-${doc.collection}`}>{doc.collection}</span>
                      </td>
                      <td>{doc.chunk_count}</td>
                      <td>
                        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                          {doc.access_roles.map(r => (
                            <span key={r} className="badge badge-role" style={{ fontSize: 11 }}>
                              {r.replace(/_/g, ' ')}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}

        {/* Stats Tab */}
        {tab === 'stats' && stats && (
          <>
            <div className="stat-grid">
              <div className="stat-card">
                <div className="stat-value">{stats.total_chunks}</div>
                <div className="stat-label">Total Chunks</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.total_users}</div>
                <div className="stat-label">Total Users</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{Object.keys(stats.chunks_by_collection).length}</div>
                <div className="stat-label">Collections</div>
              </div>
            </div>

            <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Chunks by Collection</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 32 }}>
              {Object.entries(stats.chunks_by_collection).map(([col, count]) => {
                const maxCount = Math.max(...Object.values(stats.chunks_by_collection), 1);
                return (
                  <div key={col} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{ width: 100, fontSize: 13, color: 'var(--text-secondary)' }}>{col}</span>
                    <div style={{
                      flex: 1, height: 24, background: 'var(--bg-glass)', borderRadius: 6, overflow: 'hidden',
                    }}>
                      <div style={{
                        height: '100%',
                        width: `${(count / maxCount) * 100}%`,
                        background: COLLECTION_COLORS[col] || '#6b7280',
                        borderRadius: 6,
                        transition: 'width 0.6s ease',
                        display: 'flex',
                        alignItems: 'center',
                        paddingLeft: 8,
                        fontSize: 11,
                        color: 'white',
                        fontWeight: 600,
                      }}>
                        {count}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Chunks by Type</h3>
            <div className="stat-grid">
              {Object.entries(stats.chunks_by_type).map(([type, count]) => (
                <div key={type} className="stat-card">
                  <div className="stat-value" style={{ fontSize: 24 }}>{count}</div>
                  <div className="stat-label">{type}</div>
                </div>
              ))}
            </div>

            <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, marginTop: 32 }}>Users by Role</h3>
            <div className="stat-grid">
              {Object.entries(stats.users_by_role).map(([role, count]) => (
                <div key={role} className="stat-card">
                  <div className="stat-value" style={{ fontSize: 24 }}>{count}</div>
                  <div className="stat-label">{role.replace(/_/g, ' ')}</div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
