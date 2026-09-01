import { useEffect, useMemo, useState } from 'react';
import {
  ChevronDoubleLeftIcon,
  ChevronDoubleRightIcon,
  PlusIcon,
  TrashIcon,
} from '@heroicons/react/16/solid';
import { Button } from '@heroui/react';
import cn from 'classnames';

import {
  type ConversationGroup,
  conversationTitle,
  groupConversations,
} from '~/chat/state/conversation-groups';
import type { Conversation } from '~/chat/state/types';

const COLLAPSED_KEY = 'mism-chat-sidebar-collapsed';

function readCollapsed(): boolean {
  try {
    return globalThis.localStorage?.getItem(COLLAPSED_KEY) === '1';
  } catch {
    return false;
  }
}

function writeCollapsed(collapsed: boolean): void {
  try {
    globalThis.localStorage?.setItem(COLLAPSED_KEY, collapsed ? '1' : '0');
  } catch {
    // A browser refusing storage must not stop the rail from toggling.
  }
}

function ConversationRow({
  conversation,
  isActive,
  isConfirming,
  onSelect,
  onRequestDelete,
  onConfirmDelete,
  onCancelDelete,
}: {
  conversation: Conversation;
  isActive: boolean;
  isConfirming: boolean;
  onSelect: () => void;
  onRequestDelete: () => void;
  onConfirmDelete: () => void;
  onCancelDelete: () => void;
}) {
  if (isConfirming) {
    return (
      <li className="rounded-lg bg-danger-50 px-3 py-2">
        <p className="text-xs text-default-900">Delete this conversation?</p>
        <div className="mt-2 flex gap-2">
          <button
            className="text-xs font-semibold text-danger-600 underline underline-offset-2"
            onClick={onConfirmDelete}
            type="button"
          >
            Delete
          </button>
          <button
            className="text-xs text-default-800 underline underline-offset-2"
            onClick={onCancelDelete}
            type="button"
          >
            Cancel
          </button>
        </div>
      </li>
    );
  }

  return (
    <li className="group/row relative">
      <button
        className={cn(
          'w-full rounded-lg px-3 py-2 pr-9 text-left',
          'text-xs leading-5 line-clamp-2',
          isActive
            ? 'bg-primary/10 font-semibold text-primary'
            : 'text-default-900 hover:bg-default-100'
        )}
        onClick={onSelect}
        type="button"
      >
        {conversationTitle(conversation)}
      </button>
      <button
        aria-label={`Delete conversation: ${conversationTitle(conversation)}`}
        className={cn(
          'absolute right-2 top-2 rounded p-1 text-default-800',
          'opacity-0 focus-visible:opacity-100 group-hover/row:opacity-100',
          'hover:bg-default-200 hover:text-danger-600'
        )}
        onClick={onRequestDelete}
        type="button"
      >
        <TrashIcon className="size-3.5" />
      </button>
    </li>
  );
}

export function ChatSidebar({
  conversations,
  activeId,
  onSelect,
  onNewChat,
  onDelete,
}: {
  conversations: Conversation[];
  activeId: string | undefined;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [confirmingId, setConfirmingId] = useState<string | undefined>();

  /**
   * The stored preference cannot be read during SSR, so the rail always renders
   * expanded first. Transitions stay off until the real value has painted,
   * otherwise an already-collapsed rail animates shut on every load.
   */
  const [animate, setAnimate] = useState(false);
  useEffect(() => {
    setCollapsed(readCollapsed());
    const frame = requestAnimationFrame(() => setAnimate(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  const groups: ConversationGroup[] = useMemo(
    () => groupConversations(conversations, Date.now()),
    [conversations]
  );

  function toggle() {
    setCollapsed((previous) => {
      writeCollapsed(!previous);
      return !previous;
    });
    setConfirmingId(undefined);
  }

  return (
    <aside
      aria-label="Conversation history"
      className={cn(
        // `overflow-hidden` keeps the toggle and row text inside the rail when
        // collapsed instead of spilling over the thread.
        'sticky top-16 h-[calc(100dvh-4rem)] shrink-0 overflow-hidden',
        'flex flex-col border-r border-default-200 bg-default-50',
        animate &&
          'transition-[width] duration-300 motion-reduce:transition-none',
        collapsed ? 'w-14' : 'w-[304px]'
      )}
    >
      <div
        className={cn(
          'flex shrink-0 items-center gap-2 p-3',
          collapsed && 'justify-center'
        )}
      >
        {collapsed ? undefined : (
          <h2 className="flex-1 truncate font-headline text-[13px] font-bold uppercase tracking-widest text-default-900">
            History
          </h2>
        )}
        <Button
          aria-label={collapsed ? 'Expand history' : 'Collapse history'}
          isIconOnly
          onPress={toggle}
          size="sm"
          variant="light"
        >
          {collapsed ? (
            <ChevronDoubleRightIcon className="size-4" />
          ) : (
            <ChevronDoubleLeftIcon className="size-4" />
          )}
        </Button>
      </div>

      <div className={cn('shrink-0 px-3 pb-3', collapsed && 'px-2')}>
        <Button
          aria-label="New chat"
          className={cn('font-semibold', collapsed && 'min-w-0')}
          color="primary"
          fullWidth={!collapsed}
          isIconOnly={collapsed}
          onPress={onNewChat}
          size="sm"
          startContent={collapsed ? undefined : <PlusIcon className="size-4" />}
          variant="flat"
        >
          {collapsed ? <PlusIcon className="size-4" /> : 'New chat'}
        </Button>
      </div>

      {collapsed ? undefined : (
        <>
          <nav className="min-h-0 flex-1 overflow-y-auto px-3">
            {groups.length === 0 ? (
              <p className="px-3 py-2 text-xs text-default-800">
                Questions you ask will be listed here.
              </p>
            ) : (
              groups.map((group) => (
                <section className="mb-4" key={group.label}>
                  <h3 className="px-3 py-1 text-[10px] font-bold uppercase tracking-wide text-default-800">
                    {group.label}
                  </h3>
                  <ul className="space-y-0.5">
                    {group.conversations.map((conversation) => (
                      <ConversationRow
                        conversation={conversation}
                        isActive={conversation.id === activeId}
                        isConfirming={conversation.id === confirmingId}
                        key={conversation.id}
                        onCancelDelete={() => setConfirmingId(undefined)}
                        onConfirmDelete={() => {
                          onDelete(conversation.id);
                          setConfirmingId(undefined);
                        }}
                        onRequestDelete={() => setConfirmingId(conversation.id)}
                        onSelect={() => onSelect(conversation.id)}
                      />
                    ))}
                  </ul>
                </section>
              ))
            )}
          </nav>

          <p className="shrink-0 border-t border-default-200 px-6 py-3 text-[11px] text-default-800">
            History is saved in this browser only.
          </p>
        </>
      )}
    </aside>
  );
}
