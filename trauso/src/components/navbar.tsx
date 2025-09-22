import { Box, Github, Menu } from "lucide-react";
import { ThemeToggle } from "./theme-toggle";
import { Button } from "./ui/button";
import { useState } from "react";

export function Navbar() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 w-full border-b bg-background">
      <div className="container flex h-16 items-center justify-between">
        <div className="flex items-center gap-2">
          <Box className="h-6 w-6" />
          <span className="text-lg font-bold">Terabox Downloader</span>
        </div>

        {/* Mobile menu button */}
        <Button 
          variant="ghost" 
          size="icon" 
          className="md:hidden" 
          onClick={() => setIsMenuOpen(!isMenuOpen)}
        >
          <Menu className="h-6 w-6" />
        </Button>

        {/* Desktop navigation */}
        <nav className="hidden md:flex items-center gap-6">
          <a href="#" className="text-sm font-medium hover:text-primary">
            Home
          </a>
          <a href="#" className="text-sm font-medium hover:text-primary">
            Features
          </a>
          <a href="#" className="text-sm font-medium hover:text-primary">
            About
          </a>
          <div className="flex items-center gap-2">
            <a 
              href="https://github.com/Imam-Hossain-45/terabox-downloader-cli" 
              target="_blank" 
              rel="noopener noreferrer"
            >
              <Button variant="ghost" size="icon">
                <Github className="h-5 w-5" />
              </Button>
            </a>
            <ThemeToggle />
          </div>
        </nav>

        {/* Mobile menu */}
        {isMenuOpen && (
          <div className="absolute top-16 left-0 w-full bg-background border-b md:hidden p-4">
            <nav className="flex flex-col gap-4">
              <a href="#" className="text-sm font-medium hover:text-primary">
                Home
              </a>
              <a href="#" className="text-sm font-medium hover:text-primary">
                Features
              </a>
              <a href="#" className="text-sm font-medium hover:text-primary">
                About
              </a>
              <div className="flex items-center gap-2 mt-2">
                <a 
                  href="https://github.com/Imam-Hossain-45/terabox-downloader-cli" 
                  target="_blank" 
                  rel="noopener noreferrer"
                >
                  <Button variant="ghost" size="icon">
                    <Github className="h-5 w-5" />
                  </Button>
                </a>
                <ThemeToggle />
              </div>
            </nav>
          </div>
        )}
      </div>
    </header>
  );
} 