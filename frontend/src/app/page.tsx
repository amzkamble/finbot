'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';

export default function Home() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    router.replace(isAuthenticated ? '/chat' : '/login');
  }, [isAuthenticated, router]);

  return null;
}
