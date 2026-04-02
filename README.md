# Remote Administration Tool

System administration and monitoring utility.

## Installation

### Agent
```powershell
iwr -Uri "https://github.com/damehavy/helpertool/releases/latest/download/rat-agent.exe" -OutFile agent.exe
.\agent.exe --server YOUR_IP:9876
