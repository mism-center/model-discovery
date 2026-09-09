import { useEffect, useState } from 'react';
import {
  ChevronDoubleLeftIcon,
  PlusIcon,
  TrashIcon,
} from '@heroicons/react/16/solid';
import {
  Button,
  Modal,
  ModalBody,
  ModalContent,
  ModalFooter,
  ModalHeader,
} from '@heroui/react';
import cn from 'classnames';

import {
  type ConversationGroup,
  conversationTitle,
  groupConversations,
} from '~/chat/state/conversation-groups';
import { timeAgo } from '~/chat/state/relative-time';
import type { Conversation } from '~/chat/state/types';

const COLLAPSED_KEY = 'mism-chat-sidebar-collapsed';

/** Matches the rail's own width transition so labels travel with it. */
const LABEL_TRANSITION =
  'transition-[max-width,opacity] duration-300 motion-reduce:transition-none';

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
  now,
  onSelect,
  onRequestDelete,
}: {
  conversation: Conversation;
  isActive: boolean;
  now: number;
  onSelect: () => void;
  onRequestDelete: () => void;
}) {
  const title = conversationTitle(conversation);

  return (
    /*
     * Hover styling lives on the row, not the select button, so moving onto the
     * delete control does not read as leaving the row.
     */
    <li
      className={cn(
        'group/row relative rounded-lg',
        isActive ? 'bg-primary/10' : 'hover:bg-default-100'
      )}
    >
      <button
        className="w-full rounded-lg px-2 py-2 pr-9 text-left"
        onClick={onSelect}
        type="button"
      >
        <span
          className={cn(
            'block truncate text-[13px] leading-5',
            isActive
              ? 'font-medium text-primary'
              : 'font-medium text-default-900'
          )}
        >
          {title}
        </span>
        <span className="mt-0.5 block text-[11px] text-default-800">
          {timeAgo(conversation.createdAt, now)}
        </span>
      </button>
      <button
        aria-label={`Delete conversation: ${title}`}
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
  const [pendingDelete, setPendingDelete] = useState<
    Conversation | undefined
  >();

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

  // Recomputed per render rather than on a timer: the labels are coarse enough
  // that a row reading "5 minutes ago" for a while is not wrong.
  const now = Date.now();
  const groups: ConversationGroup[] = groupConversations(conversations, now);

  function toggle() {
    setCollapsed((previous) => {
      writeCollapsed(!previous);
      return !previous;
    });
  }

  return (
    <>
      <aside
        aria-label="Conversation history"
        className={cn(
          // `overflow-hidden` keeps the toggle and row text inside the rail
          // when collapsed instead of spilling over the thread.
          'sticky top-16 h-[calc(100dvh-4rem)] shrink-0 overflow-hidden',
          'flex flex-col border-r border-default-200 bg-default-50',
          animate &&
            'transition-[width] duration-300 motion-reduce:transition-none',
          collapsed ? 'w-14' : 'w-[304px]'
        )}
      >
        {/*
         * Labels collapse to zero width alongside the rail rather than being
         * swapped out, so the buttons travel with the animation instead of
         * snapping into their compact form on the first frame.
         */}
        <div
          className={cn(
            'flex shrink-0 items-center p-3',
            animate &&
              'transition-[gap] duration-300 motion-reduce:transition-none',
            collapsed ? 'gap-0' : 'gap-2'
          )}
        >
          <h2
            className={cn(
              'overflow-hidden whitespace-nowrap font-headline text-[13px] font-bold uppercase tracking-widest text-default-900',
              animate && LABEL_TRANSITION,
              collapsed ? 'max-w-0 opacity-0' : 'max-w-full flex-1 opacity-100'
            )}
          >
            History
          </h2>
          <Button
            aria-label={collapsed ? 'Expand history' : 'Collapse history'}
            isIconOnly
            onPress={toggle}
            size="sm"
            variant="light"
          >
            <ChevronDoubleLeftIcon
              className={cn(
                'size-4',
                animate &&
                  'transition-transform duration-300 motion-reduce:transition-none',
                collapsed && 'rotate-180'
              )}
            />
          </Button>
        </div>

        <div className="shrink-0 px-3 pb-3">
          <Button
            aria-label="New chat"
            className="min-w-0 px-0 font-semibold"
            color="primary"
            fullWidth
            onPress={onNewChat}
            size="sm"
          >
            <span
              className={cn(
                'flex items-center justify-center overflow-hidden',
                animate &&
                  'transition-[gap] duration-300 motion-reduce:transition-none',
                collapsed ? 'gap-0' : 'gap-2'
              )}
            >
              <PlusIcon className="size-4 shrink-0" />
              <span
                className={cn(
                  'overflow-hidden whitespace-nowrap',
                  animate && LABEL_TRANSITION,
                  collapsed ? 'max-w-0 opacity-0' : 'max-w-[8rem] opacity-100'
                )}
              >
                New chat
              </span>
            </span>
          </Button>
        </div>

        {/*
         * Kept mounted and faded rather than unmounted, so collapsing reads as
         * one movement instead of the contents vanishing before the rail moves.
         */}
        <div
          aria-hidden={collapsed}
          className={cn(
            'flex min-h-0 flex-1 flex-col',
            animate &&
              'transition-opacity duration-200 motion-reduce:transition-none',
            collapsed && 'pointer-events-none opacity-0'
          )}
        >
          <nav className="min-h-0 w-[304px] flex-1 overflow-y-auto px-3">
            {groups.length === 0 ? (
              <p className="px-2 py-2 text-xs text-default-800">
                Questions you ask will be listed here.
              </p>
            ) : (
              groups.map((group) => (
                <section className="mb-4" key={group.label}>
                  <h3 className="px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-default-800">
                    {group.label}
                  </h3>
                  <ul className="mt-0.5 space-y-0.5">
                    {group.conversations.map((conversation) => (
                      <ConversationRow
                        conversation={conversation}
                        isActive={conversation.id === activeId}
                        key={conversation.id}
                        now={now}
                        onRequestDelete={() => setPendingDelete(conversation)}
                        onSelect={() => onSelect(conversation.id)}
                      />
                    ))}
                  </ul>
                </section>
              ))
            )}
          </nav>

          <p className="w-[304px] shrink-0 border-t border-default-200 px-3 py-3 text-[11px] text-default-800">
            History is saved in this browser only.
          </p>
        </div>
      </aside>

      <Modal
        classNames={{
          backdrop: 'bg-slate-900/50 backdrop-blur-sm',
          base: 'border border-default-200',
        }}
        hideCloseButton
        isOpen={pendingDelete !== undefined}
        // `onOpenChange` is the controlled pairing for `isOpen`; with only
        // `onClose`, react-aria keeps its own open state and ignores the prop.
        onOpenChange={(open) => {
          if (!open) setPendingDelete(undefined);
        }}
        size="sm"
      >
        <ModalContent>
          <ModalHeader className="flex items-start gap-3 px-5 pb-0 pt-5">
            <span className="min-w-0 flex-1">
              <span className="block font-headline text-base leading-6 tracking-tight text-default-900">
                Delete this conversation?
              </span>
              <span className="mt-0.5 block truncate text-xs font-normal text-default-800">
                {pendingDelete ? conversationTitle(pendingDelete) : ''}
              </span>
            </span>
          </ModalHeader>
          <ModalBody className="px-5 py-4">
            <p className="text-sm font-light leading-relaxed text-default-800">
              History is saved in this browser only, so deleting this
              conversation cannot be reversed.
            </p>
          </ModalBody>
          <ModalFooter className="gap-2 border-t border-default-200 px-5 py-3">
            <Button
              onPress={() => setPendingDelete(undefined)}
              size="sm"
              variant="light"
            >
              Cancel
            </Button>
            <Button
              className="font-semibold"
              color="primary"
              onPress={() => {
                if (pendingDelete) onDelete(pendingDelete.id);
                setPendingDelete(undefined);
              }}
              size="sm"
              startContent={<TrashIcon className="size-3.5" />}
            >
              Delete
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </>
  );
}
