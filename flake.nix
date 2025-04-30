{
  description = "An opinionated collection of utility scripts";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    systems.url = "github:nix-systems/default-linux"; #we add support for aarch64-linux
    flake-utils = {
      url = "github:numtide/flake-utils";
      inputs.systems.follows = "systems";
    };
  };

  outputs = { self, nixpkgs, flake-utils, ... }: 

    flake-utils.lib.eachDefaultSystem (system: #this function just does everything for every system that we defined above in: inputs.systems.url

    let
      # Define your specific system
      #system = "x86_64-linux"; # Change this if you're on a different architecture
      
      # Get pkgs for your system
      pkgs = import nixpkgs { inherit system; };
    in {
      # Define the package for your system
      packages.default = pkgs.callPackage ./default.nix {};
      
      # Expose as an overlay for easier integration
      overlays.default = final: prev: {
        personal-scripts = self.packages.${prev.system}.default;
      };

      devShells = {  ## Adev shell with all the deps of my-toolkit available (with "$ nix shell .... " command, the deps are not available (like ffmpeg) )
          default = pkgs.mkShell {
            packages = [ self.packages.${system}.default ];
            inputsFrom = [ self.packages.${system}.default ];
          };
        };
      
      # NixOS module for easy addition to your system configuration
      nixosModules = { config, lib, pkgs, ... }: {
        options = {
          my-toolkit = {
            enable = lib.mkEnableOption "Enable my-toolkit";
            services = {
              media-renamer = lib.mkEnableOption "Enable media-renamer service";
              ebook-organizer = lib.mkEnableOption "Enable ebook-organizer service";
            };
          };
        };

        config = lib.mkIf config.my-toolkit.enable {
          environment.systemPackages = [ 
            self.packages.default
            pkgs.python311
          ];

          # Define systemd services conditionally
          systemd.user.services = lib.mkMerge [
            (lib.mkIf config.my-toolkit.services.media-renamer {
              media-renamer = {
                description = "Screenshot and Screencast Renamer Service";
                wantedBy = [ "default.target" ];
                path = [ pkgs.inotify-tools pkgs.zenity ];
                serviceConfig = {
                  ExecStart = "${self.packages.default}/bin/media-renamer";
                  Restart = "always";
                  RestartSec = "5";
                  StandardOutput = "journal";
                  StandardError = "journal";
                };
              };
            })
            (lib.mkIf config.my-toolkit.services.ebook-organizer {
              ebook-organizer = {
                description = "E-book Organizer Service";
                wantedBy = [ "default.target" ];
                path = [ 
                  pkgs.calibre 
                  pkgs.zenity 
                  pkgs.inotify-tools 
                  pkgs.procps 
                  pkgs.dbus 
                ];
                serviceConfig = {
                  ExecStart = "${self.packages.default}/bin/ebook-organizer";
                  Restart = "always";
                  RestartSec = "5";
                  StandardOutput = "journal";
                  StandardError = "journal";
                };
              };
            })
          ];
        };
      };
    }
    );
}
