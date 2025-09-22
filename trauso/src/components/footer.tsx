import { Github } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t bg-background">
      <div className="container flex flex-col items-center justify-between gap-4 py-10 md:h-24 md:flex-row md:py-0">
        <div className="flex flex-col items-center gap-4 px-8 md:flex-row md:gap-2 md:px-0">
          <p className="text-center text-sm leading-loose text-muted-foreground md:text-left">
            Built with ❤️ by{" "}
            <a
              href="https://github.com/Imam-Hossain-45"
              target="_blank"
              rel="noreferrer"
              className="font-medium underline underline-offset-4"
            >
              Imam Hossain
            </a>
            . The source code is available on{" "}
            <a
              href="https://github.com/Imam-Hossain-45/terabox-downloader-cli"
              target="_blank"
              rel="noreferrer"
              className="font-medium underline underline-offset-4"
            >
              GitHub
            </a>
            .
          </p>
        </div>
        <div className="flex items-center">
          <a
            href="https://github.com/Imam-Hossain-45/terabox-downloader-cli"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 text-sm font-medium"
          >
            <Github className="h-5 w-5" />
            <span>GitHub</span>
          </a>
        </div>
      </div>
    </footer>
  );
} 