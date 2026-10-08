let currentStationIsNew = false;

export function setCurrentStationIsNew(value: unknown) {
    currentStationIsNew = Boolean(value);
}

export function isCurrentStationNew() {
    return currentStationIsNew;
}
