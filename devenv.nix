{
  pkgs,
  lib,
  config,
  inputs,
  ...
}:
let
  buildInputs = with pkgs; [
    stdenv.cc.cc.lib
    stdenv.cc.cc
    stdenv.cc
    libuv
    zlib
    #gperftools
    #libGLU
    #libGL
    #glib
  ];
in
{
  # https://devenv.sh/basics/
  env.GREET = "devenv";

  # disable dotenv hint
  dotenv.disableHint = true;

  # https://devenv.sh/packages/
  packages = with pkgs; [
    git
    ruff
  ];

  # https://devenv.sh/languages/
  languages.python = {
    enable = true;
    version = "3.12";
    venv = {
      enable = true;
    };
    uv = {
      enable = true;
    };
  };

  # https://devenv.sh/processes/
  # processes.dev.exec = "${lib.getExe pkgs.watchexec} -n -- ls -la";

  # https://devenv.sh/services/
  # services.postgres.enable = true;

  # https://devenv.sh/basics/
  enterShell = ''
    #export PATH="${pkgs.ninja}/bin:$PATH"
    echo "Python version: $(python --version)"
    echo "UV version: $(uv --version)"
    git --version
  '';

  # https://devenv.sh/tasks/
  # tasks = {
  #   "myproj:setup".exec = "mytool build";
  #   "devenv:enterShell".after = [ "myproj:setup" ];
  # };

  # https://devenv.sh/tests/
  # enterTest = ''
  #   echo "Running tests"
  #   git --version | grep --color=auto "${pkgs.git.version}"
  # '';

  # https://devenv.sh/git-hooks/
  # git-hooks.hooks.shellcheck.enable = true;

  # See full reference at https://devenv.sh/reference/options/
}
