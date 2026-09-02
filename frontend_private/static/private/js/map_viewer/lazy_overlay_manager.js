/**
 * Race-safe lifecycle for one logical overlay owning one or more map objects.
 * Visibility is deliberately session-only; callers own persistence if desired.
 */
export class LazyOverlayManager {
    constructor(options) {
        this.options = options;
        this.desired = new Map();
        this.loading = new Map();
        this.generations = new Map();
        this.inflight = new Map();
        this.cache = new Map();
        this.registrations = new Map();
        this.entities = new Map();
        this.maxCacheEntries = options.maxCacheEntries ?? Number.POSITIVE_INFINITY;
    }

    isDesired(id) { return this.desired.get(String(id)) === true; }
    isLoading(id) { return this.loading.get(String(id)) === true; }
    getRegistration(id) { return this.registrations.get(String(id)) || null; }

    _version(entity) {
        return String(this.options.getVersion(entity) || 'unversioned');
    }

    _nextGeneration(id) {
        const key = String(id);
        const next = (this.generations.get(key) || 0) + 1;
        this.generations.set(key, next);
        return next;
    }

    _isCurrent(id, generation, version) {
        const key = String(id);
        const entity = this.entities.get(key);
        return this.isDesired(key)
            && this.generations.get(key) === generation
            && entity
            && this._version(entity) === version;
    }

    _setLoading(id, value) {
        const key = String(id);
        this.loading.set(key, value);
        this.options.onStateChange?.(key, { desired: this.isDesired(key), loading: value });
    }

    async setDesired(entity, desired) {
        const id = String(entity.id);
        this.entities.set(id, entity);
        const version = this._version(entity);
        const existingRequest = this.inflight.get(id);
        if (desired === true && this.isDesired(id) && existingRequest?.version === version) {
            return existingRequest.promise;
        }
        this.desired.set(id, desired === true);
        const generation = this._nextGeneration(id);

        if (!desired) {
            this.inflight.get(id)?.controller.abort();
            this.inflight.delete(id);
            this._setLoading(id, false);
            await this.options.setVisible(this.registrations.get(id), false, entity);
            await this._evict();
            return false;
        }

        const cached = this.cache.get(id);
        if (cached?.version === version && this.registrations.has(id)) {
            cached.lastUsed = Date.now();
            await this.options.setVisible(this.registrations.get(id), true, entity);
            if (!this._isCurrent(id, generation, version)) {
                await this.options.setVisible(this.registrations.get(id), false, entity);
                return false;
            }
            this.options.onStateChange?.(id, { desired: true, loading: false });
            return true;
        }

        this.inflight.get(id)?.controller.abort();
        const controller = new AbortController();
        this._setLoading(id, true);
        const promise = this._load(entity, { id, generation, version, controller });
        this.inflight.set(id, { controller, generation, version, promise });
        return promise;
    }

    async _load(entity, request) {
        const { id, generation, version, controller } = request;
        let registration = null;
        try {
            const data = await this.options.fetchData(entity, controller.signal);
            if (!this._isCurrent(id, generation, version)) return false;

            const previous = this.registrations.get(id);
            if (previous) {
                await this.options.remove(previous, entity);
                if (this.registrations.get(id) === previous) {
                    this.registrations.delete(id);
                    this.cache.delete(id);
                }
                if (!this._isCurrent(id, generation, version)) return false;
            }
            registration = await this.options.attach(entity, data, {
                generation,
                signal: controller.signal,
                version,
            });
            if (!this._isCurrent(id, generation, version)) {
                await this.options.remove(registration, entity);
                return false;
            }

            this.registrations.set(id, registration);
            this.cache.set(id, { version, data, lastUsed: Date.now() });
            await this.options.setVisible(registration, true, entity);
            if (!this._isCurrent(id, generation, version)) {
                await this.options.setVisible(registration, false, entity);
                return false;
            }
            await this._evict();
            return true;
        } catch (error) {
            if (registration && this.registrations.get(id) === registration) {
                try {
                    await this.options.remove(registration, entity);
                } catch (cleanupError) {
                    console.error(`Failed to clean up overlay ${id} after activation error`, cleanupError);
                }
                this.registrations.delete(id);
                this.cache.delete(id);
            }
            if (error?.name !== 'AbortError' && this.generations.get(id) === generation) {
                this.desired.set(id, false);
                this.options.onError?.(id, error, entity);
            }
            return false;
        } finally {
            if (this.inflight.get(id)?.generation === generation) this.inflight.delete(id);
            if (this.generations.get(id) === generation) this._setLoading(id, false);
        }
    }

    async invalidate(id, { preserveDesired = true } = {}) {
        const key = String(id);
        this._nextGeneration(key);
        this.inflight.get(key)?.controller.abort();
        this.inflight.delete(key);
        const registration = this.registrations.get(key);
        if (registration) await this.options.remove(registration, this.entities.get(key));
        this.registrations.delete(key);
        this.cache.delete(key);
        this._setLoading(key, false);
        if (!preserveDesired) this.desired.delete(key);
    }

    async reconcile(entities) {
        const next = new Map(entities.map(entity => [String(entity.id), entity]));
        for (const [id, oldEntity] of this.entities) {
            const newEntity = next.get(id);
            if (!newEntity) {
                await this.invalidate(id, { preserveDesired: false });
                this.entities.delete(id);
            } else if (this._version(oldEntity) !== this._version(newEntity)) {
                const wasDesired = this.isDesired(id);
                this.entities.set(id, newEntity);
                await this.invalidate(id, { preserveDesired: true });
                if (wasDesired) await this.setDesired(newEntity, true);
            } else {
                this.entities.set(id, newEntity);
            }
        }
        for (const [id, entity] of next) if (!this.entities.has(id)) this.entities.set(id, entity);
    }

    async restoreDesired() {
        await Promise.all([...this.entities.values()].filter(entity => this.isDesired(entity.id))
            .map(entity => this.setDesired(entity, true)));
    }

    async markRegistrationsRemoved() {
        for (const [id, request] of this.inflight) {
            this._nextGeneration(id);
            request.controller.abort();
        }
        this.inflight.clear();
        await Promise.all([...this.registrations.entries()].map(([id, registration]) => (
            this.options.remove(registration, this.entities.get(id))
        )));
        this.registrations.clear();
        for (const id of this.loading.keys()) this._setLoading(id, false);
    }

    async _evict() {
        if (this.cache.size <= this.maxCacheEntries) return;
        const candidates = [...this.cache.entries()]
            .filter(([id]) => !this.isDesired(id) && !this.isLoading(id))
            .sort((a, b) => a[1].lastUsed - b[1].lastUsed);
        while (this.cache.size > this.maxCacheEntries && candidates.length) {
            const [id] = candidates.shift();
            await this.invalidate(id, { preserveDesired: true });
        }
    }
}
