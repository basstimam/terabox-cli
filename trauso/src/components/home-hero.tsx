import { Download, FileDown, Link, Upload } from "lucide-react";
import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "./ui/card";
import { Input } from "./ui/input";
import { useState } from "react";

export function HomeHero() {
  const [url, setUrl] = useState("");

  const handleDownload = () => {
    // Handle download functionality
    console.log("Downloading from URL:", url);
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] px-4 py-10">
      <div className="text-center mb-8">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl">
          Terabox <span className="text-primary">Downloader</span>
        </h1>
        <p className="mt-4 text-xl text-muted-foreground max-w-3xl mx-auto">
          Download files from Terabox quickly and easily without any restrictions
        </p>
      </div>

      <Card className="w-full max-w-2xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Download className="h-5 w-5" />
            Download Files
          </CardTitle>
          <CardDescription>
            Paste your Terabox link below to start downloading
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2">
              <Link className="h-5 w-5 text-muted-foreground" />
              <Input 
                placeholder="https://terabox.com/s/..." 
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="flex-1"
              />
            </div>
          </div>
        </CardContent>
        <CardFooter>
          <Button 
            onClick={handleDownload} 
            className="w-full" 
            disabled={!url}
          >
            <FileDown className="mr-2 h-4 w-4" /> Download Now
          </Button>
        </CardFooter>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-16 w-full max-w-5xl">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Download className="h-5 w-5" />
              Fast Downloads
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p>Download files at maximum speed without any throttling or limitations</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="h-5 w-5" />
              Bulk Downloads
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p>Download multiple files and folders at once with our efficient downloader</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileDown className="h-5 w-5" />
              No Restrictions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p>No file size limits, no waiting time, no registration required</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
} 