{
  description = "An opinionated collection of utility scripts";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs, ... }: 
    let
      # Define your specific system
      system = "x86_64-linux"; # Change this if you're on a different architecture
      
      # Get pkgs for your system
      pkgs = import nixpkgs { inherit system; };
    in {
      # Define the package for your system
      packages.${system} = {
        default = pkgs.callPackage ./default.nix {};
      };
      
      # Expose as an overlay for easier integration
      overlays.default = final: prev: {
        personal-scripts = self.packages.${prev.system}.default;
      };
      
      # NixOS module for easy addition to your system configuration
      nixosModules.default = { config, lib, pkgs, ... }: {
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
            self.packages.${pkgs.system}.default
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
                  ExecStart = "${self.packages.${pkgs.system}.default}/bin/media-renamer";
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
                  ExecStart = "${self.packages.${pkgs.system}.default}/bin/ebook-organizer";
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
    };
}
