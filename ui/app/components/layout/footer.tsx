import headerLogoVertical from './MISM-large-text-crop.png';

export function Footer() {
  return (
    <footer className="w-full bg-background py-8 border-t-1 border-default">
      <div className="container mx-auto px-8">
        <div className="flex flex-col">
          <img src={headerLogoVertical} alt="MISM Logo" className="w-40 pl-[1.5px] pb-2" />
          <p className="font-bold text-xl text-secondary">Multiscale Model Portal</p>
        </div>
      </div>
    </footer>
  )
}