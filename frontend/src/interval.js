/**
 * Little wrapper that emulates setInterval() but with methods, and
 * takes the time callback() takes to resolve into account.
 */
export class Interval {
	#timeout;

	constructor(interval, callback) {
		this.interval = interval;
		this.callback = callback;
	}
	
	start() {
		if (this.#timeout)
			clearTimeout(this.#timeout);
		this.#timeout = setTimeout(this.#callback.bind(this), this.interval);
	}

	stop() {
		clearTimeout(this.#timeout);
		this.#timeout = null;
	}

	restart() {
		this.stop();
		this.start();
	}

	#callback() {
		// Wait for the callback() to resolve in case it is
		// async, and then schedule a new call.
		Promise.resolve(this.callback()).then(() => {
			if (this.#timeout)
				this.start()
		})
	}
}