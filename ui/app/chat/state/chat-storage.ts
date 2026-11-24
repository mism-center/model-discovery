import type { Conversation } from './types';

const DATABASE_NAME = 'mism-chat';
const DATABASE_VERSION = 1;
const STORE_NAME = 'conversations';

/**
 * Conversations are held in IndexedDB rather than localStorage: one answer
 * measures ~118KB with its evidence, so a handful of turns would exhaust a 5MB
 * origin quota. IndexedDB's quota is disk-proportional and it stores structured
 * clones, so the raw CAIRNS response is kept whole.
 */
function storageAvailable(): boolean {
  return globalThis.indexedDB !== undefined;
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.addEventListener('upgradeneeded', () => {
      if (!request.result.objectStoreNames.contains(STORE_NAME)) {
        request.result.createObjectStore(STORE_NAME, { keyPath: 'id' });
      }
    });
    request.addEventListener('success', () => resolve(request.result));
    request.addEventListener('error', () => reject(request.error));
  });
}

function promisify<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.addEventListener('success', () => resolve(request.result));
    request.addEventListener('error', () => reject(request.error));
  });
}

/**
 * Persistence is a convenience, never a precondition for using the page:
 * private-mode restrictions and quota errors must not break sending a question.
 */
function warn(operation: string, error: unknown): void {
  console.warn(`chat storage ${operation} failed`, error);
}

export async function loadConversations(): Promise<Conversation[]> {
  if (!storageAvailable()) return [];
  try {
    const database = await openDatabase();
    const store = database
      .transaction(STORE_NAME, 'readonly')
      .objectStore(STORE_NAME);
    const conversations = await promisify(
      store.getAll() as IDBRequest<Conversation[]>
    );
    database.close();
    return conversations;
  } catch (error) {
    warn('load', error);
    return [];
  }
}

export async function saveConversation(
  conversation: Conversation
): Promise<void> {
  if (!storageAvailable()) return;
  try {
    const database = await openDatabase();
    const store = database
      .transaction(STORE_NAME, 'readwrite')
      .objectStore(STORE_NAME);
    await promisify(store.put(conversation));
    database.close();
  } catch (error) {
    warn('save', error);
  }
}

export async function deleteConversation(id: string): Promise<void> {
  if (!storageAvailable()) return;
  try {
    const database = await openDatabase();
    const store = database
      .transaction(STORE_NAME, 'readwrite')
      .objectStore(STORE_NAME);
    await promisify(store.delete(id));
    database.close();
  } catch (error) {
    warn('delete', error);
  }
}
