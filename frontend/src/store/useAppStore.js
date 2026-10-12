import { create } from 'zustand';

const loadRecent = () => {
  try { return JSON.parse(localStorage.getItem('recentSearches') || '[]'); } catch { return []; }
};

const useAppStore = create((set, get) => ({
  recentSearches: loadRecent(),
  watchlist: [],
  addRecent: (ticker) => {
    const updated = [ticker, ...get().recentSearches.filter((t) => t !== ticker)].slice(0, 10);
    localStorage.setItem('recentSearches', JSON.stringify(updated));
    set({ recentSearches: updated });
  },
  toggleWatchlist: (ticker) => {
    const wl = get().watchlist;
    const next = wl.includes(ticker) ? wl.filter((t) => t !== ticker) : [...wl, ticker];
    set({ watchlist: next });
  },
}));

export default useAppStore;
