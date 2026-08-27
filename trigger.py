class TriggerLogic:
    @staticmethod
    def calculate_intensity(damage: float, config):
        use_dynamic = config.get("use_dynamic", True)
        if not use_dynamic:
            return config.get("strength", 50)
        if damage <= 0:
            return config.get("min_intensity", 20)
        max_damage = config.get("max_damage_mapping", 50)
        min_intensity = config.get("min_intensity", 20)
        max_intensity = config.get("max_intensity", 100)
        ratio = min(damage / max_damage, 1.0)
        intensity = min_intensity + int((max_intensity - min_intensity) * ratio)
        return min(max(intensity, min_intensity), max_intensity)

    @staticmethod
    def should_trigger(health, threshold, triggered):
        return health < threshold and not triggered