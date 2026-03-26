import { SearchProvider } from '../../../contexts/search-context';
import { SearchBar } from './search-bar/search-bar';
import { SearchSidebar } from './search-sidebar';
import { SearchResults } from './search-results/search-results';

function SearchSectionContent() {
  return (
    <main className="flex flex-col grow">
      <div className="grid grid-cols-[auto_minmax(0,1fr)] grid-rows-[auto_minmax(0,1fr)] grow items-stretch bg-default-50">
        <div className="col-start-1 col-span-2 row-start-1">
          <div className="flex flex-col w-full h-full">
            <SearchBar />
          </div>
        </div>

        <div className="self-start ml-0 col-start-1 row-start-2 row-span-1">
          <div className="shrink-0 overflow-hidden w-full h-full">
            <SearchSidebar />
          </div>
        </div>

        <div className="col-start-2 row-start-2 border-x border-slate-200 mr-0 bg-white">
          <div className="flex items-stretch grow w-full h-full">
            <SearchResults />
          </div>
        </div>
      </div>
    </main>
  );
}

export default function SearchSection() {
  return (
    <SearchProvider>
      <SearchSectionContent />
    </SearchProvider>
  );
}
