import { useEffect, useState } from 'react';
import {
  Navbar,
  NavbarBrand,
  NavbarContent,
  NavbarItem,
  Dropdown,
  DropdownTrigger,
  DropdownMenu,
  DropdownItem,
  Button,
  Input,
  Skeleton,
  type DropdownItemProps,
  extendVariants,
} from '@heroui/react';
import {
  Link as RouterLink,
  NavLink,
  useLocation,
  useNavigate,
  useSearchParams,
} from 'react-router';
import cn from 'classnames';
import {
  ArrowRightStartOnRectangleIcon,
  BoltIcon,
  ChevronDownIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/16/solid';

import { signIn, signOut, useUser, type CurrentUser } from '~/api/auth/user';

interface NavbarDropdownItemProps extends DropdownItemProps {
  isActive?: boolean;
}

const NavbarDropdownItem = extendVariants(DropdownItem, {
  variants: {
    isActive: {
      true: {
        base: 'bg-primary-100! hover:bg-primary-200!',
        title: 'text-primary!',
        description: 'text-primary!',
      },
      false: {
        base: 'hover:bg-default-200!',
      },
    },
  },
  slots: {
    base: '[&>div]:gap-1 p-3',
    title: 'font-semibold text-default-900 text-[15px]',
    description: 'text-sm text-default-800 max-w-[300px] text-wrap',
  },
}) as React.FC<NavbarDropdownItemProps>;

function HeaderSearchBar() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const searchQuery = searchParams.get('q') ?? '';
  const [currentSearch, setCurrentSearch] = useState(searchQuery);

  useEffect(() => {
    setCurrentSearch(searchQuery);
  }, [searchQuery]);

  const doSearch = (query: string) => {
    const params = new URLSearchParams();
    if (query) params.set('q', query);
    setSearchParams(params);
  };

  return (
    <div className="flex items-center gap-2 p-1">
      <form
        className="flex items-center"
        onSubmit={(e) => {
          e.preventDefault();
          doSearch(currentSearch);
        }}
      >
        <div
          className={cn(
            'flex items-center w-70 lg:w-90',
            'bg-white/10 border border-white/20 rounded-lg',
            'focus-within:bg-white/15 focus-within:ring-2 focus-within:ring-white/10',
            'transition-all duration-300'
          )}
        >
          <Input
            classNames={{
              input: 'text-[13px] !text-white placeholder-slate-400',
              inputWrapper: 'shadow-none bg-transparent! pl-2 min-h-8 h-8',
            }}
            placeholder="Search models & data..."
            value={currentSearch}
            onValueChange={setCurrentSearch}
            isClearable
            startContent={
              <MagnifyingGlassIcon className="size-5 text-slate-400 mr-1" />
            }
          />
        </div>
      </form>
      <Button
        size="sm"
        className={cn(
          'h-8 px-3 py-2 rounded-md shrink-0',
          'bg-white border border-white/25 text-primary',
          'hover:bg-white/90 opacity-100! transition-colors duration-200'
        )}
        variant="flat"
        startContent={<BoltIcon className="size-4 scale-x-75" />}
        onPress={() => navigate('/chat')}
      >
        <span className="text-[13px] font-bold">AI Mode</span>
      </Button>
    </div>
  );
}

function displayName(user: CurrentUser): string {
  return user.name || user.preferred_username || user.email || user.sub;
}

function initials(user: CurrentUser): string {
  const name = user.name?.trim();
  if (name) {
    const parts = name.split(/\s+/);
    const first = parts[0][0] ?? '';
    const last = parts.length > 1 ? (parts.at(-1)?.[0] ?? '') : '';
    return (first + last).toUpperCase();
  }
  return displayName(user).slice(0, 2).toUpperCase();
}

function UserAvatar({
  user,
  className,
}: {
  user: CurrentUser;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={cn(
        'flex items-center justify-center rounded-full select-none',
        'bg-secondary font-medium text-white',
        className
      )}
    >
      {initials(user)}
    </span>
  );
}

function HeaderAuth() {
  const { user, isLoading } = useUser();

  if (isLoading && user === null) {
    return <Skeleton className="rounded-full h-8 w-8 bg-white/20" />;
  }

  if (!user) {
    return (
      <button
        className={cn(
          'text-slate-300 hover:text-white transition-colors',
          'text-[0.9375rem] px-1 py-1.5 font-medium tracking-tight shrink-0'
        )}
        onClick={() => signIn()}
      >
        Sign in
      </button>
    );
  }

  const name = displayName(user);

  return (
    <Dropdown
      placement="bottom-end"
      classNames={{
        content: cn(
          'min-w-60 p-1.5 rounded-xl',
          'bg-white/95 backdrop-blur-md border border-default-300',
          'shadow-xl shadow-primary-900/15'
        ),
      }}
    >
      <DropdownTrigger>
        <Button
          isIconOnly
          disableRipple
          aria-label="Account menu"
          className="group size-8 min-w-0 rounded-full shrink-0 bg-transparent opacity-100! scale-100!"
        >
          <UserAvatar
            user={user}
            className={cn(
              'size-8 text-xs transition-colors duration-200',
              'group-data-[hover=true]:bg-secondary-600'
            )}
          />
        </Button>
      </DropdownTrigger>
      <DropdownMenu
        aria-label="Account menu"
        className="p-0 gap-1"
        itemClasses={{ base: 'rounded-lg' }}
      >
        <DropdownItem
          key="identity"
          isReadOnly
          className={cn(
            'opacity-100! cursor-default p-2.5 mb-1',
            'bg-default-100/75 data-[hover=true]:bg-default-100/75'
          )}
          textValue={user.email ?? name}
        >
          <div className="flex items-center gap-2.5">
            <UserAvatar user={user} className="size-9 text-[13px] shrink-0" />
            <div className="min-w-0">
              <div className="text-sm font-semibold text-default-900 truncate">
                {name}
              </div>
              {user.email && user.email !== name && (
                <div className="text-xs text-default-700 truncate">
                  {user.email}
                </div>
              )}
            </div>
          </div>
        </DropdownItem>
        <DropdownItem
          key="signout"
          startContent={<ArrowRightStartOnRectangleIcon className="size-4" />}
          className={cn(
            'px-2.5 py-2',
            'data-[hover=true]:bg-default-300',
            'data-[pressed=true]:bg-default'
          )}
          onPress={() => {
            void signOut();
          }}
        >
          <span className="text-[13px] font-medium">Sign out</span>
        </DropdownItem>
      </DropdownMenu>
    </Dropdown>
  );
}

export function Header() {
  const { pathname } = useLocation();
  const [searchParams] = useSearchParams();
  const { user } = useUser();

  const navLinkClassnames = ({ isActive }: { isActive: boolean }) =>
    cn(
      isActive
        ? 'text-white border-b-2 border-success pb-1'
        : 'text-slate-300 hover:text-white transition-colors',
      'text-[0.9375rem] mx-3 px-1 py-1.5! font-medium tracking-tight'
    );

  const isSearchActive = pathname.toLowerCase().startsWith('/search');
  const isChatActive = pathname.toLowerCase().startsWith('/chat');
  const isCatalogActive = pathname.toLowerCase().startsWith('/catalog');
  const isDiscoverActive = isSearchActive || isChatActive || isCatalogActive;

  const isSearchCompact = isSearchActive && !!searchParams.get('q');

  return (
    <Navbar
      maxWidth="full"
      className="sticky shadow-sm px-2 bg-linear-to-r from-[#000f3c] to-[#012169] text-white [&>header]:justify-start"
    >
      <NavbarBrand className="grow-0">
        <RouterLink to="/" className="flex items-center">
          {/* <HeaderLogo className="h-8 w-auto" /> */}
          <span className="text-2xl font-black text-white tracking-tighter font-headline">
            MISM
          </span>
        </RouterLink>
      </NavbarBrand>
      <NavbarContent justify="center" className="gap-1 ml-3">
        <Dropdown placement="bottom-end" radius="sm">
          <NavbarItem>
            <DropdownTrigger>
              <button
                className={cn(
                  navLinkClassnames({ isActive: isDiscoverActive }),
                  'scale-none! opacity-100! flex items-center'
                )}
              >
                Discover
                <ChevronDownIcon className="size-5 ml-1 -mr-1" />
              </button>
            </DropdownTrigger>
          </NavbarItem>
          <DropdownMenu aria-label="Search options">
            <NavbarDropdownItem
              key="search"
              title="Search"
              description="Find models and datasets using keywords"
              href="/search"
              isActive={isSearchActive}
            />
            <NavbarDropdownItem
              key="assistant"
              title="Assistant"
              description="Find models and datasets by asking questions"
              href="/chat"
              isActive={isChatActive}
            />
            <NavbarDropdownItem
              key="catalog"
              title="Catalog"
              description="Browse models and datasets by category"
              href="/catalog"
              isActive={isCatalogActive}
            />
          </DropdownMenu>
        </Dropdown>
        {/* `/upload` and `/runs` are both `requireUser`-gated, so the links are
            hidden rather than left to bounce an anonymous visitor through login
            to reach a page they were never offered a reason to want. */}
        {user && (
          <>
            <NavbarItem>
              <NavLink to="/upload" className={navLinkClassnames}>
                Upload
              </NavLink>
            </NavbarItem>
            <NavbarItem>
              <NavLink to="/runs" className={navLinkClassnames}>
                My Runs
              </NavLink>
            </NavbarItem>
          </>
        )}
        <NavbarItem>
          <NavLink to="/about" className={navLinkClassnames}>
            About
          </NavLink>
        </NavbarItem>
      </NavbarContent>
      <NavbarContent justify="end" className="flex-1 gap-2">
        {isSearchActive && (
          <NavbarItem className="flex justify-end flex-1">
            <div
              className="grid"
              style={{
                gridTemplateColumns: isSearchCompact ? '1fr' : '0fr',
                transitionProperty: 'grid-template-columns',
                transitionDuration: '200ms',
                transitionTimingFunction: 'cubic-bezier(0.4, 0, 0.2, 1)',
              }}
            >
              <div className="overflow-hidden">
                <HeaderSearchBar />
              </div>
            </div>
          </NavbarItem>
        )}
        <NavbarItem>
          <HeaderAuth />
        </NavbarItem>
      </NavbarContent>
    </Navbar>
  );
}
