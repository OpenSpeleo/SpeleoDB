let currentStationIsNew = false;

export function setCurrentStationIsNew(value) {
    currentStationIsNew = Boolean(value);
}

export function isCurrentStationNew() {
    return currentStationIsNew;
}
