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

function HeaderAuth() {
  const { user, isLoading } = useUser();

  if (isLoading && user === null) {
    return <Skeleton className="rounded-md h-8 w-20" />;
  }

  if (!user) {
    return (
      <Button
        size="sm"
        variant="flat"
        className={cn(
          'h-8 px-3 py-2 rounded-md shrink-0',
          'bg-white border border-white/25 text-primary',
          'hover:bg-white/90 opacity-100! transition-colors duration-200',
          'text-[13px] font-bold'
        )}
        onPress={() => signIn()}
      >
        Sign in
      </Button>
    );
  }

  const name = displayName(user);

  return (
    <Dropdown placement="bottom-end" radius="sm">
      <DropdownTrigger>
        <Button
          size="sm"
          variant="flat"
          endContent={<ChevronDownIcon className="size-4 -mr-1" />}
          className={cn(
            'h-8 px-3 py-2 rounded-md shrink-0',
            'bg-white/10 border border-white/20 text-white',
            'hover:bg-white/15 opacity-100! transition-colors duration-200',
            'text-[13px] font-semibold'
          )}
        >
          {name}
        </Button>
      </DropdownTrigger>
      <DropdownMenu aria-label="Account menu" className="min-w-56">
        <DropdownItem
          key="identity"
          isReadOnly
          showDivider
          className="opacity-100! cursor-default data-[hover=true]:bg-transparent"
          textValue={user.email ?? name}
        >
          <div className="text-[11px] uppercase tracking-wide text-default-700">
            Signed in as
          </div>
          <div className="text-sm font-semibold text-default-900 truncate">
            {user.email ?? name}
          </div>
        </DropdownItem>
        <DropdownItem
          key="signout"
          color="danger"
          className="text-danger font-medium"
          onPress={() => {
            void signOut();
          }}
        >
          Sign out
        </DropdownItem>
      </DropdownMenu>
    </Dropdown>
  );
}

export function Header() {
  const { pathname } = useLocation();
  const [searchParams] = useSearchParams();

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
        <NavbarItem>
          <NavLink to="/upload" className={navLinkClassnames}>
            Upload
          </NavLink>
        </NavbarItem>
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
