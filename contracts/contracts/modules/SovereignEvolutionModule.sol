// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SovereignEvolutionModule
 * @notice Manages the transition of a user's Safe from Stage 1 (Convenience) to Stage 2 (Sovereign).
 */
contract SovereignEvolutionModule {
    enum Stage { Stage1_Convenience, Stage2_Sovereign }

    struct SafeConfig {
        Stage currentStage;
        address backendSigner;
        address[] guardians;
    }

    mapping(address => SafeConfig) public safeConfigs;

    event StageUpgraded(address indexed safe, Stage newStage);
    event BackendSignerRevoked(address indexed safe, address backendSigner);
    event GuardiansAdded(address indexed safe, address[] guardians);

    modifier onlySafe() {
        // In a real module, we verify msg.sender is the Safe proxy
        _;
    }

    /**
     * @notice Initialize a new Safe config at Stage 1
     */
    function initializeSafe(address _backendSigner) external {
        require(safeConfigs[msg.sender].backendSigner == address(0), "Already initialized");
        
        safeConfigs[msg.sender].currentStage = Stage.Stage1_Convenience;
        safeConfigs[msg.sender].backendSigner = _backendSigner;
    }

    /**
     * @notice Evolve to Stage 2: Revoke backend signer and add guardians
     * @param _guardians Array of at least 2 guardian addresses for social recovery
     */
    function promoteToSovereign(address[] calldata _guardians) external onlySafe {
        SafeConfig storage config = safeConfigs[msg.sender];
        require(config.currentStage == Stage.Stage1_Convenience, "Must be Stage 1");
        require(_guardians.length >= 2, "Requires at least 2 guardians");

        // Revoke the backend signer (irreversible)
        address revokedSigner = config.backendSigner;
        config.backendSigner = address(0);

        // Add the Social Guardians
        config.guardians = _guardians;

        // Upgrade the Stage
        config.currentStage = Stage.Stage2_Sovereign;

        emit BackendSignerRevoked(msg.sender, revokedSigner);
        emit GuardiansAdded(msg.sender, _guardians);
        emit StageUpgraded(msg.sender, Stage.Stage2_Sovereign);
    }

    /**
     * @notice Get current safe configuration
     */
    function getSafeConfig(address safe) external view returns (Stage, address, address[] memory) {
        SafeConfig memory config = safeConfigs[safe];
        return (config.currentStage, config.backendSigner, config.guardians);
    }
}