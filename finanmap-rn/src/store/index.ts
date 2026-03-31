/**
 * FinanMap Pro — Global Store (Zustand)
 * Estado persistido via AsyncStorage
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { RiskProfile, OnboardingResult, FireResult, GAResult } from '../services/api';

// ── Types ─────────────────────────────────────────────────────────────────────

interface UserProfile {
  nome:           string;
  perfil:         RiskProfile;
  score:          number;
  patrimonio:     number;
  aporte:         number;
  despesas:       number;
  horizonte:      number;
  incluirCripto:  boolean;
  alloc:          Record<string, number>;
  onboardingDone: boolean;
}

interface AppState {
  // Usuário
  user:           UserProfile | null;
  setUser:        (u: Partial<UserProfile>) => void;
  clearUser:      () => void;

  // Onboarding
  onboardingResult: OnboardingResult | null;
  setOnboardingResult: (r: OnboardingResult) => void;

  // FIRE
  fireResult:     FireResult | null;
  setFireResult:  (r: FireResult) => void;

  // GA / Robôs
  gaResult:       GAResult | null;
  setGAResult:    (r: GAResult) => void;
  robots:         Robot[];
  setRobots:      (r: Robot[]) => void;

  // Market
  marketData:     any | null;
  setMarketData:  (d: any) => void;
  lastMarketFetch:number;
  setLastMarketFetch:(t: number) => void;

  // UI
  isLoading:      boolean;
  setLoading:     (v: boolean) => void;
}

export interface Robot {
  id:      number;
  emoji:   string;
  name:    string;
  strain:  string;
  genes:   Record<string, number>;
  fit:     number;
  cagr:    number;
  status:  'elite' | 'mutante' | 'extinto' | 'normal';
  gen:     number;
}

// ── Store ─────────────────────────────────────────────────────────────────────

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      user:              null,
      onboardingResult:  null,
      fireResult:        null,
      gaResult:          null,
      robots:            [],
      marketData:        null,
      lastMarketFetch:   0,
      isLoading:         false,

      setUser:   (u)  => set(s => ({ user: { ...s.user, ...u } as UserProfile })),
      clearUser: ()   => set({ user: null, onboardingResult: null, fireResult: null }),

      setOnboardingResult: (r) => set({ onboardingResult: r }),
      setFireResult:       (r) => set({ fireResult: r }),
      setGAResult:         (r) => set({ gaResult: r }),
      setRobots:           (r) => set({ robots: r }),
      setMarketData:       (d) => set({ marketData: d }),
      setLastMarketFetch:  (t) => set({ lastMarketFetch: t }),
      setLoading:          (v) => set({ isLoading: v }),
    }),
    {
      name:    'finanmap-store',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: (s) => ({
        user:             s.user,
        onboardingResult: s.onboardingResult,
        fireResult:       s.fireResult,
        robots:           s.robots,
      }),
    },
  ),
);
