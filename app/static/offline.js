(function () {
  const DB_NAME = "taxiops-offline";
  const STORE = "sync-queue";

  function openDB() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        req.result.createObjectStore(STORE, { keyPath: "id" });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  window.syncQueue = {
    async add(entry) {
      const db = await openDB();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, "readwrite");
        tx.objectStore(STORE).put(entry);
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
    },

    async getAll() {
      const db = await openDB();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, "readonly");
        const req = tx.objectStore(STORE).getAll();
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
      });
    },

    async remove(id) {
      const db = await openDB();
      return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, "readwrite");
        tx.objectStore(STORE).delete(id);
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
    },
  };

  async function syncPending() {
    const entries = await window.syncQueue.getAll();
    for (const entry of entries) {
      if (entry.synced) continue;
      const endpoint = entry.taxi_id && entry.start_time
        ? "/api/breakdowns"
        : "/api/income";
      try {
        const resp = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(entry),
        });
        if (resp.ok) {
          entry.synced = true;
          await window.syncQueue.remove(entry.id);
        }
      } catch {
        // will retry next tick
      }
    }
  }

  if (navigator.onLine) {
    syncPending();
  }
  window.addEventListener("online", syncPending);
})();
