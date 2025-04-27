# Systemd Services

This directory contains systemd service definitions for various automated tasks. These services are designed to run in the user context and can be enabled or disabled individually through the NixOS configuration.

## Available Services

### Media Renamer
**File**: `media-renamer.sh`
**Description**: Monitors for new screenshots and screencasts, then renames them according to a specified format. Uses inotify-tools to watch for file changes and zenity for any necessary user interactions.

### E-book Organizer
**File**: `ebook-organizer.sh`
**Description**: Monitors a designated directory for new EPUB files. When a new e-book is detected, it prompts for a new name, creates a dedicated folder, and converts the EPUB to AZW3 format using Calibre's ebook-convert.

## Usage

### Enabling Services

To enable these services, add the following to your `configuration.nix`:

```nix
{
  my-toolkit.enable = true;
  my-toolkit.services = {
    media-renamer = true;
    ebook-organizer = true;
  };
}
```

After making changes, rebuild your system:
```bash
sudo nixos-rebuild switch
```

### Checking Service Status

You can check the status of all services using:
```bash
my-toolkit list
```

Or check individual services using systemctl:
```bash
systemctl --user status media-renamer
systemctl --user status ebook-organizer
```

## Adding New Services

To add a new service:

1. Create your shell script in the `systemd_services` directory (e.g., `my-service.sh`)
2. Add the service to the options in [`flake.nix`](/flake.nix)::
   ```nix
   options = {
     my-toolkit = {
       services = {
         my-service = lib.mkEnableOption "Enable my-service";
       };
     };
   };
   ```
3. Add the service to the configuration in [`flake.nix`](/flake.nix):
   ```nix
   systemd.user.services = lib.mkMerge [
     (lib.mkIf config.my-toolkit.services.my-service {
       my-service = {
         description = "My Service Description";
         wantedBy = [ "default.target" ];
         path = [ pkgs.required-dependencies ];
         serviceConfig = {
           ExecStart = "${self.packages.${pkgs.system}.default}/bin/my-service";
           Restart = "always";
           RestartSec = "5";
           StandardOutput = "journal";
           StandardError = "journal";
         };
       };
     })
   ];
   ```

## Viewing Logs

To view logs for your systemd services, you can use the `journalctl` command. Here are some useful commands for viewing logs:

1. View logs for a specific user service:
   ```
   journalctl --user -u service-name
   ```
   For example, to view logs for the media-renamer service:
   ```
   journalctl --user -u media-renamer
   ```

2. View logs in real-time (follow mode):
   ```
   journalctl -f --user -u service-name
   ```

3. View logs since the last boot:
   ```
   journalctl --user -u service-name -b
   ```

4. View logs for a specific time range:
   ```
   journalctl --user -u service-name --since "2023-01-01" --until "2023-01-02"
   ```

5. View only error and higher priority messages:
   ```
   journalctl --user -u service-name -p err
   ```

6. View a specific number of recent log entries:
   ```
   journalctl --user -u service-name -n 50
   ```

Replace `service-name` with the name of your service as defined in your NixOS configuration.

## Useful Commands

To manage and monitor your systemd services, you can use the following commands:

- List all user services: `systemctl --user list-units --type=service`
- View service status: `systemctl --user status service-name`
- Start a service: `systemctl --user start service-name`
- Stop a service: `systemctl --user stop service-name`
- Restart a service: `systemctl --user restart service-name`
- Enable a service to start on boot: `systemctl --user enable service-name`
- Disable a service from starting on boot: `systemctl --user disable service-name`

Remember to replace `service-name` with the actual name of your service as defined in your NixOS configuration.