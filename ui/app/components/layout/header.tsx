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
  SparklesIcon,
} from '@heroicons/react/16/solid';
import HeaderLogo from './MISM icon.svg?react';

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

export function Header() {
  const { pathname } = useLocation();
  const [searchParams] = useSearchParams();

  const navLinkClassnames = ({ isActive }: { isActive: boolean }) =>
    cn(
      isActive
        ? 'text-white border-b-2 border-success pb-1'
        : 'text-slate-300 hover:text-white transition-colors',
      'text-[0.9375rem] mx-3 px-1 py-1.5! font-medium tracking-tight',
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
                  'scale-none! opacity-100! flex items-center',
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
      {isSearchActive && (
        <NavbarContent justify="end" className="flex-1">
          <NavbarItem className="flex justify-end w-full">
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
        </NavbarContent>
      )}
    </Navbar>
  );
}
